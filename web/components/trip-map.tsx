'use client';

// Trip map, adapted from a-donde-ir's recommender-map. Loads only in the browser (next/dynamic). MapLibre with
// OpenFreeMap's Positron style: no key, commercial use allowed, attribution required.
//
// Every station is a faint dot for context. Candidates near the destination are coloured by P(free dock) on a
// one-hue sequential ramp (light → dark = less → more likely free); rank 1 and 2 are larger and labelled. The start is
// the only accent-filled point; the bike pickup is an accent ring and the destination an ink ring. A double click on
// the map sets the destination; a click on a station opens its predictions. Colours come from globals.css.

import { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { Candidate, Pickup, Station } from '@/lib/api';

export const BASEMAP_STYLE = 'https://tiles.openfreemap.org/styles/positron';
// Served from public/ (scripts/copy-worker.mjs): bundled, MapLibre cannot find its worker next to itself.
const WORKER_URL = '/maplibre-gl-worker.mjs';
const CIRCLE_STEPS = 64;
const DOUBLE_CLICK_MS = 400;
const DOUBLE_CLICK_PX = 12;
// P(free dock) bands; must match the legend in planner.tsx.
export const FREE_STEPS = [0.5, 0.8, 0.95];

export type Point = { lat: number; lng: number };
export type Inset = { top: number; bottom: number; left: number; right: number };

function circle({ lat, lng }: Point, km: number): GeoJSON.Feature {
  const coords: [number, number][] = [];
  for (let i = 0; i <= CIRCLE_STEPS; i++) {
    const a = (i / CIRCLE_STEPS) * 2 * Math.PI;
    coords.push([lng + (km / (111.32 * Math.cos((lat * Math.PI) / 180))) * Math.cos(a), lat + (km / 111.32) * Math.sin(a)]);
  }
  return { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: coords } };
}

function cubicBezier(x1: number, y1: number, x2: number, y2: number) {
  const at = (a: number, b: number, s: number) => 3 * a * s * (1 - s) ** 2 + 3 * b * s ** 2 * (1 - s) + s ** 3;
  const slope = (a: number, b: number, s: number) => 3 * a * (1 - s) ** 2 + 6 * (b - a) * s * (1 - s) + 3 * (1 - b) * s ** 2;
  return (t: number) => {
    let s = t;
    for (let i = 0; i < 8; i++) {
      const d = slope(x1, x2, s);
      if (Math.abs(d) < 1e-6) break;
      s = Math.min(1, Math.max(0, s - (at(x1, x2, s) - t) / d));
    }
    return at(y1, y2, s);
  };
}

function easeOut() {
  const css = getComputedStyle(document.documentElement).getPropertyValue('--ease-out');
  const n = css.match(/-?[\d.]+/g)?.map(Number);
  return n && n.length === 4 ? cubicBezier(n[0], n[1], n[2], n[3]) : cubicBezier(0.22, 1, 0.36, 1);
}

const collection = (features: GeoJSON.Feature[]): GeoJSON.FeatureCollection => ({ type: 'FeatureCollection', features });
const point = (p: Point, properties: Record<string, unknown> = {}): GeoJSON.Feature => ({
  type: 'Feature',
  properties,
  geometry: { type: 'Point', coordinates: [p.lng, p.lat] },
});

/** Station names come from the Ecobici feed: escape them before they go into popup HTML. */
const esc = (v: unknown) =>
  String(v ?? '—').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);

const pct = (p: number | null | undefined) => (p == null ? '—' : `${Math.round(p * 100)} %`);
const STATE_TEXT: Record<string, string> = { available: 'Available', full: 'Full', unavailable: 'Out of service', stale: 'Not reporting' };

function stationPopup(s: Station, c?: Candidate) {
  const lines = [
    `<b>${esc(s.name)}</b>`,
    `${esc(STATE_TEXT[s.state] ?? s.state)} · ${esc(s.docks)} free docks of ${esc(s.capacity)} · ${esc(s.bikes)} bikes`,
  ];
  if (c && c.p_free != null) lines.push(`Free dock when you arrive: <b>${pct(c.p_free)}</b> (ride ${Math.round(c.ride_min)} min)`);
  else if (s.p_full) lines.push(`Full in 15 / 30 / 45 min: ${pct(s.p_full['15'])} / ${pct(s.p_full['30'])} / ${pct(s.p_full['45'])}`);
  else lines.push('No prediction');
  return lines.join('<br/>');
}

export default function TripMap({
  center,
  stations,
  start,
  goal,
  pickup,
  candidates,
  radiusM,
  inset,
  onPickGoal,
}: {
  center: Point;
  stations: Station[];
  start: Point | null;
  goal: Point | null;
  pickup: Pickup | null;
  candidates: Candidate[];
  radiusM: number;
  /** Map area covered by the dock and the card: the camera centres on what stays visible. */
  inset: Inset;
  onPickGoal: (p: Point) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const pickGoal = useRef(onPickGoal);
  const lookup = useRef<{ stations: Map<string, Station>; candidates: Map<string, Candidate> }>({ stations: new Map(), candidates: new Map() });
  const [broken, setBroken] = useState(false);
  // Layers exist only after the style loads; a draw asked for earlier waits here.
  const ready = useRef(false);
  const pending = useRef<(() => void) | null>(null);
  pickGoal.current = onPickGoal;
  lookup.current = {
    stations: new Map(stations.map((s) => [s.id, s])),
    candidates: new Map(candidates.map((c) => [c.id, c])),
  };

  useEffect(() => {
    if (!box.current) return;
    const css = getComputedStyle(document.documentElement);
    const v = (name: string) => css.getPropertyValue(name).trim();
    const [ink, paper, accent, faint, none] = ['--ink', '--paper', '--accent', '--dot', '--no-data'].map(v);
    const ramp = ['--free-0', '--free-1', '--free-2', '--free-3'].map(v);
    let m: maplibregl.Map;
    maplibregl.setWorkerUrl(WORKER_URL);
    try {
      m = new maplibregl.Map({ container: box.current, style: BASEMAP_STYLE, center: [center.lng, center.lat], zoom: 12, attributionControl: false });
    } catch {
      setBroken(true); // No WebGL, no map; the panel still works.
      return;
    }
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    // OpenFreeMap and OpenStreetMap require a visible credit. The dock covers the bottom.
    m.addControl(new maplibregl.AttributionControl({ compact: true }), 'top-left');
    m.on('load', () => {
      for (const id of ['stations', 'radius', 'path', 'candidates', 'pickup', 'goal', 'start']) m.addSource(id, { type: 'geojson', data: collection([]) });
      m.addLayer({
        id: 'stations',
        type: 'circle',
        source: 'stations',
        paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 2, 15, 4], 'circle-color': faint },
      });
      m.addLayer({ id: 'radius', type: 'line', source: 'radius', paint: { 'line-color': ink, 'line-opacity': 0.45, 'line-width': 1, 'line-dasharray': [3, 2] } });
      m.addLayer({ id: 'path', type: 'line', source: 'path', paint: { 'line-color': ink, 'line-opacity': 0.55, 'line-width': 2 }, layout: { 'line-cap': 'round', 'line-join': 'round' } });
      m.addLayer({
        id: 'candidates',
        type: 'circle',
        source: 'candidates',
        paint: {
          'circle-radius': ['case', ['<=', ['coalesce', ['get', 'rank'], 99], 2], 11, 7],
          'circle-color': [
            'case',
            ['==', ['get', 'p_free'], -1],
            none,
            ['step', ['get', 'p_free'], ramp[0], FREE_STEPS[0], ramp[1], FREE_STEPS[1], ramp[2], FREE_STEPS[2], ramp[3]],
          ],
          'circle-stroke-color': paper,
          'circle-stroke-width': 2,
        },
      });
      m.addLayer({
        id: 'ranks',
        type: 'symbol',
        source: 'candidates',
        filter: ['<=', ['coalesce', ['get', 'rank'], 99], 2],
        layout: { 'text-field': ['to-string', ['get', 'rank']], 'text-font': ['Noto Sans Bold'], 'text-size': 12, 'text-allow-overlap': true },
        paint: { 'text-color': paper },
      });
      m.addLayer({ id: 'pickup', type: 'circle', source: 'pickup', paint: { 'circle-radius': 13, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': accent, 'circle-stroke-width': 3 } });
      m.addLayer({ id: 'goal', type: 'circle', source: 'goal', paint: { 'circle-radius': 15, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': ink, 'circle-stroke-width': 3 } });
      m.addLayer({ id: 'start', type: 'circle', source: 'start', paint: { 'circle-radius': 8, 'circle-color': accent, 'circle-stroke-color': paper, 'circle-stroke-width': 3 } });
      ready.current = true;
      pending.current?.();
      pending.current = null;
    });

    const popup = new maplibregl.Popup({ closeButton: true, closeOnClick: true, offset: 12, maxWidth: '280px' });
    for (const layer of ['candidates', 'stations']) {
      m.on('mouseenter', layer, () => (m.getCanvas().style.cursor = 'pointer'));
      m.on('mouseleave', layer, () => (m.getCanvas().style.cursor = ''));
    }
    // Double click = two click events, not dblclick: on phones a double tap does not always fire dblclick.
    m.doubleClickZoom.disable();
    let last = { time: -Infinity, x: 0, y: 0 };
    m.on('click', (e) => {
      const layers = ['candidates', 'stations'].filter((l) => m.getLayer(l));
      const hit = layers.length ? m.queryRenderedFeatures(e.point, { layers })[0] : undefined;
      if (hit) {
        const id = String(hit.properties.id);
        const s = lookup.current.stations.get(id);
        if (s) popup.setLngLat([s.lng, s.lat]).setHTML(stationPopup(s, lookup.current.candidates.get(id))).addTo(m);
        return;
      }
      const time = e.originalEvent.timeStamp;
      const double = time - last.time < DOUBLE_CLICK_MS && Math.hypot(e.point.x - last.x, e.point.y - last.y) < DOUBLE_CLICK_PX;
      last = double ? { time: -Infinity, x: 0, y: 0 } : { time, x: e.point.x, y: e.point.y };
      if (double) pickGoal.current({ lat: e.lngLat.lat, lng: e.lngLat.lng });
    });
    map.current = m;
    return () => {
      m.remove();
      map.current = null;
      ready.current = false;
    };
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const draw = () => {
      const set = (id: string, f: GeoJSON.Feature[]) => (m.getSource(id) as maplibregl.GeoJSONSource).setData(collection(f));
      const near = new Set(candidates.map((c) => c.id));
      set('stations', stations.filter((s) => !near.has(s.id)).map((s) => point(s, { id: s.id })));
      set(
        'candidates',
        // Best last, so it draws on top.
        [...candidates].reverse().map((c) => point(c, { id: c.id, rank: c.rank, p_free: c.p_free ?? -1 })),
      );
      set('start', start ? [point(start)] : []);
      set('goal', goal ? [point(goal)] : []);
      set('pickup', pickup && start && (pickup.lat !== start.lat || pickup.lng !== start.lng) ? [point(pickup)] : []);
      set('radius', goal ? [circle(goal, radiusM / 1000 / 1.3)] : []);
      const best = candidates.find((c) => c.rank === 1);
      const line = [start, pickup, best].filter(Boolean) as Point[];
      set('path', line.length > 1 ? [{ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: line.map((p) => [p.lng, p.lat]) } }] : []);
    };
    if (ready.current) draw();
    else pending.current = draw;
  }, [stations, start, goal, pickup, candidates, radiusM]);

  useEffect(() => {
    map.current?.setPadding(inset);
  }, [inset.top, inset.bottom, inset.left, inset.right]);

  // Frame the trip when its ends change.
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const ends = [start, goal].filter(Boolean) as Point[];
    if (!ends.length) return;
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const padding = { top: inset.top + 40, bottom: inset.bottom + 40, left: inset.left + 40, right: inset.right + 40 };
    if (ends.length === 1) {
      m.easeTo({ center: [ends[0].lng, ends[0].lat], zoom: Math.max(m.getZoom(), 14), padding: inset, duration: still ? 0 : 900, easing: easeOut() });
      return;
    }
    const b = new maplibregl.LngLatBounds();
    for (const p of ends) b.extend([p.lng, p.lat]);
    m.fitBounds(b, { padding, maxZoom: 15.5, duration: still ? 0 : 900, easing: easeOut() });
  }, [start?.lat, start?.lng, goal?.lat, goal?.lng]);

  if (broken) return <p className="notice">Your browser cannot show the map. The plan below still works.</p>;
  return <div ref={box} className="stage__mapbox" role="application" aria-label="Map. Double click to set the destination." />;
}
