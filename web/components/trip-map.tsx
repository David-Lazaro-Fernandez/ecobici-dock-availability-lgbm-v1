'use client';

// Trip map, adapted from the a-donde-ir recommender map. It loads only in the browser (next/dynamic).
// Basemap: OpenFreeMap Positron. No key, commercial use allowed, credit required. Colours come from globals.css.

import { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { Candidate, Pickup, Station } from '@/lib/api';
import type { Leg } from '@/lib/routes';
import { pct } from '@/lib/format';

export const BASEMAP_STYLE = 'https://tiles.openfreemap.org/styles/positron';
// Served from public/ (scripts/copy-worker.mjs). When bundled, MapLibre cannot find the worker next to its module.
const WORKER_URL = '/maplibre-gl-worker.mjs';
const CIRCLE_STEPS = 64;
const DOUBLE_CLICK_MS = 400;
const DOUBLE_CLICK_PX = 12;
// P(free dock) bands. Keep them equal to the legend in planner.tsx.
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

// The tip of the pin is the destination: the marker uses anchor 'bottom'.
const GOAL_PIN_SVG = `<svg viewBox="0 0 24 32" width="28" height="37" aria-hidden="true">
  <path d="M12 1C6 1 1.5 5.6 1.5 11.3 1.5 19 12 31 12 31s10.5-12 10.5-19.7C22.5 5.6 18 1 12 1Z"
    fill="var(--ink)" stroke="var(--paper)" stroke-width="2" />
  <circle cx="12" cy="11.3" r="4" fill="var(--paper)" />
</svg>`;

const collection = (features: GeoJSON.Feature[]): GeoJSON.FeatureCollection => ({ type: 'FeatureCollection', features });
const point = (p: Point, properties: Record<string, unknown> = {}): GeoJSON.Feature => ({
  type: 'Feature',
  properties,
  geometry: { type: 'Point', coordinates: [p.lng, p.lat] },
});

/** Station names come from the Ecobici feed. Escape them before they go into popup HTML. */
const esc = (v: unknown) =>
  String(v ?? '—').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);

const STATE_TEXT: Record<string, string> = { available: 'Disponible', full: 'Llena', unavailable: 'Fuera de servicio', stale: 'Sin datos recientes' };

function stationPopup(s: Station, c?: Candidate) {
  const lines = [
    `<b>${esc(s.name)}</b>`,
    `${esc(STATE_TEXT[s.state] ?? s.state)} · ${esc(s.docks)} lugares libres de ${esc(s.capacity)} · ${esc(s.bikes)} bicis`,
  ];
  if (c && c.p_free != null) lines.push(`Lugar libre al llegar: <b>${pct(c.p_free)}</b>`);
  else if (s.p_full) lines.push(`Llena en 15 / 30 / 45 min: ${pct(s.p_full['15'])} / ${pct(s.p_full['30'])} / ${pct(s.p_full['45'])}`);
  else lines.push('Sin pronóstico');
  if (!c && s.p_empty?.['15'] != null) lines.push(`Sin bicis en 15 min: ${pct(s.p_empty['15'])}`);
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
  legs,
  selectedId,
  onSelect,
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
  /** The trip's legs (lib/routes.ts): street routes, or straight lines until they arrive. */
  legs: Leg[];
  /** The chosen drop-off. A click on a candidate station selects it. */
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** The map area under the dock and the card. The camera centres on the visible area. */
  inset: Inset;
  onPickGoal: (p: Point) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const goalPin = useRef<maplibregl.Marker | null>(null);
  const pickGoal = useRef(onPickGoal);
  const select = useRef(onSelect);
  const lookup = useRef<{ stations: Map<string, Station>; candidates: Map<string, Candidate> }>({ stations: new Map(), candidates: new Map() });
  const [broken, setBroken] = useState(false);
  // The layers exist only after the style loads. An earlier draw waits here.
  const ready = useRef(false);
  const pending = useRef<(() => void) | null>(null);
  pickGoal.current = onPickGoal;
  select.current = onSelect;
  lookup.current = {
    stations: new Map(stations.map((s) => [s.id, s])),
    candidates: new Map(candidates.map((c) => [c.id, c])),
  };

  useEffect(() => {
    if (!box.current) return;
    const css = getComputedStyle(document.documentElement);
    const v = (name: string) => css.getPropertyValue(name).trim();
    const [ink, paper, startAndPickup, stationOutsideTrip, stationNoForecast, routeLine] = [
      '--ink',
      '--paper',
      '--start-and-pickup',
      '--station-outside-trip',
      '--station-no-forecast',
      '--route-line',
    ].map(v);
    const [freeLessThan50, free50To80, free80To95, free95OrMore] = [
      '--free-less-than-50',
      '--free-50-to-80',
      '--free-80-to-95',
      '--free-95-or-more',
    ].map(v);
    const byFreeDock: maplibregl.ExpressionSpecification = [
      'step',
      ['get', 'p_free'],
      freeLessThan50,
      FREE_STEPS[0],
      free50To80,
      FREE_STEPS[1],
      free80To95,
      FREE_STEPS[2],
      free95OrMore,
    ];
    let m: maplibregl.Map;
    maplibregl.setWorkerUrl(WORKER_URL);
    try {
      m = new maplibregl.Map({ container: box.current, style: BASEMAP_STYLE, center: [center.lng, center.lat], zoom: 12, attributionControl: false });
    } catch {
      // No WebGL, no map. The rest of the page still works.
      setBroken(true);
      return;
    }
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    // OpenFreeMap and OpenStreetMap require a visible credit. The dock covers the bottom.
    m.addControl(
      new maplibregl.AttributionControl({ compact: true, customAttribution: 'Rutas: OSRM, FOSSGIS' }),
      'top-left',
    );
    m.on('load', () => {
      for (const id of ['stations', 'radius', 'walk', 'bike', 'candidates', 'pickup', 'start']) m.addSource(id, { type: 'geojson', data: collection([]) });
      m.addLayer({
        id: 'stations',
        type: 'circle',
        source: 'stations',
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 2.5, 15, 5],
          'circle-color': stationOutsideTrip,
          'circle-stroke-color': paper,
          'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 11, 0, 14, 1],
        },
      });
      m.addLayer({ id: 'radius', type: 'line', source: 'radius', paint: { 'line-color': ink, 'line-opacity': 0.45, 'line-width': 1, 'line-dasharray': [3, 2] } });
      // Riding: solid line. Walking: dotted line. A straight leg (no route yet) is fainter.
      const opacity: maplibregl.ExpressionSpecification = ['case', ['get', 'routed'], 0.8, 0.35];
      m.addLayer({ id: 'bike', type: 'line', source: 'bike', paint: { 'line-color': routeLine, 'line-opacity': opacity, 'line-width': 3.5 }, layout: { 'line-cap': 'round', 'line-join': 'round' } });
      m.addLayer({ id: 'walk', type: 'line', source: 'walk', paint: { 'line-color': routeLine, 'line-opacity': opacity, 'line-width': 2.5, 'line-dasharray': [0.1, 2] }, layout: { 'line-cap': 'round', 'line-join': 'round' } });
      m.addLayer({
        id: 'candidates',
        type: 'circle',
        source: 'candidates',
        paint: {
          'circle-radius': ['case', ['get', 'selected'], 13, ['<=', ['coalesce', ['get', 'rank'], 99], 2], 11, 7],
          'circle-color': ['case', ['==', ['get', 'p_free'], -1], stationNoForecast, byFreeDock],
          // Ink, not green: a green ring disappears on a green station.
          'circle-stroke-color': ['case', ['get', 'selected'], ink, paper],
          'circle-stroke-width': ['case', ['get', 'selected'], 3, 2],
        },
      });
      m.addLayer({
        id: 'ranks',
        type: 'symbol',
        source: 'candidates',
        filter: ['<=', ['coalesce', ['get', 'rank'], 99], 2],
        layout: { 'text-field': ['to-string', ['get', 'rank']], 'text-font': ['Noto Sans Bold'], 'text-size': 12, 'text-allow-overlap': true },
        // White is 2.27:1 on the lightest band, so use ink there.
        paint: { 'text-color': ['case', ['<', ['get', 'p_free'], FREE_STEPS[0]], ink, paper] },
      });
      m.addLayer({ id: 'pickup', type: 'circle', source: 'pickup', paint: { 'circle-radius': 13, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': startAndPickup, 'circle-stroke-width': 3 } });
      m.addLayer({ id: 'start', type: 'circle', source: 'start', paint: { 'circle-radius': 8, 'circle-color': startAndPickup, 'circle-stroke-color': paper, 'circle-stroke-width': 3 } });
      ready.current = true;
      pending.current?.();
      pending.current = null;
    });

    const popup = new maplibregl.Popup({ closeButton: true, closeOnClick: true, offset: 12, maxWidth: '280px' });
    for (const layer of ['candidates', 'stations']) {
      m.on('mouseenter', layer, () => (m.getCanvas().style.cursor = 'pointer'));
      m.on('mouseleave', layer, () => (m.getCanvas().style.cursor = ''));
    }
    // Detect a double click from two click events: on phones, a double tap does not always fire dblclick.
    m.doubleClickZoom.disable();
    let last = { time: -Infinity, x: 0, y: 0 };
    m.on('click', (e) => {
      const layers = ['candidates', 'stations'].filter((l) => m.getLayer(l));
      const hit = layers.length ? m.queryRenderedFeatures(e.point, { layers })[0] : undefined;
      if (hit) {
        const id = String(hit.properties.id);
        const s = lookup.current.stations.get(id);
        const c = lookup.current.candidates.get(id);
        if (c?.recommendable) select.current(id);
        if (s) popup.setLngLat([s.lng, s.lat]).setHTML(stationPopup(s, c)).addTo(m);
        return;
      }
      const time = e.originalEvent.timeStamp;
      const double = time - last.time < DOUBLE_CLICK_MS && Math.hypot(e.point.x - last.x, e.point.y - last.y) < DOUBLE_CLICK_PX;
      last = double ? { time: -Infinity, x: 0, y: 0 } : { time, x: e.point.x, y: e.point.y };
      if (double) pickGoal.current({ lat: e.lngLat.lat, lng: e.lngLat.lng });
    });
    map.current = m;
    return () => {
      goalPin.current = null;
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
      // With a trip, show only the stations near the destination. Hide the layer, not its opacity: a transparent
      // circle still takes clicks.
      m.setLayoutProperty('stations', 'visibility', candidates.length ? 'none' : 'visible');
      set(
        'candidates',
        // Draw order: the selected station last, then the best, so they are on top.
        [...candidates]
          .reverse()
          .sort((a, b) => Number(a.id === selectedId) - Number(b.id === selectedId))
          .map((c) => point(c, { id: c.id, rank: c.rank, p_free: c.p_free ?? -1, selected: c.id === selectedId })),
      );
      set('start', start ? [point(start)] : []);
      if (goal) {
        if (!goalPin.current) {
          const el = document.createElement('div');
          el.className = 'goal-pin';
          el.innerHTML = GOAL_PIN_SVG;
          goalPin.current = new maplibregl.Marker({ element: el, anchor: 'bottom' });
        }
        goalPin.current.setLngLat([goal.lng, goal.lat]).addTo(m);
      } else {
        goalPin.current?.remove();
      }
      set('pickup', pickup && start && (pickup.lat !== start.lat || pickup.lng !== start.lng) ? [point(pickup)] : []);
      set('radius', goal ? [circle(goal, radiusM / 1000 / 1.3)] : []);
      const lines = (mode: string) =>
        legs
          .filter((l) => l.mode === mode)
          .map((l): GeoJSON.Feature => ({ type: 'Feature', properties: { routed: l.routed }, geometry: { type: 'LineString', coordinates: l.coords } }));
      set('walk', lines('walk'));
      set('bike', lines('bike'));
    };
    if (ready.current) draw();
    else pending.current = draw;
  }, [stations, start, goal, pickup, candidates, radiusM, legs, selectedId]);

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

  if (broken) return <p className="notice">Tu navegador no puede mostrar el mapa. El plan sigue funcionando.</p>;
  return <div ref={box} className="stage__mapbox" role="application" aria-label="Mapa. Haz doble clic para elegir el destino." />;
}
