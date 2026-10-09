'use client';

// Trip map, adapted from the a-donde-ir recommender map. It loads only in the browser (next/dynamic).
// Basemap: OpenFreeMap Positron. No key, commercial use allowed, credit required. Colours come from globals.css.

import { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { Candidate, Pickup, Station } from '@/lib/api';
import type { Leg } from '@/lib/routes';
import { pct } from '@/lib/format';
import { type Lang, type Messages, MESSAGES } from '@/lib/i18n';
import { isPhone } from '@/lib/phone';

export const BASEMAP_STYLE = 'https://tiles.openfreemap.org/styles/positron';
// Positron layers recolored with the palette of the help illustrations. A layer that the style drops is skipped.
type ColorPaint = 'background-color' | 'fill-color' | 'fill-outline-color' | 'line-color';
const BASEMAP_PAINT: [layer: string, property: ColorPaint, cssVar: string][] = [
  ['background', 'background-color', '--map-land'],
  ['road_area_pier', 'fill-color', '--map-land'],
  ['road_pier', 'line-color', '--map-land'],
  ['landuse_residential', 'fill-color', '--map-residential'],
  ['park', 'fill-color', '--map-park'],
  ['landcover_wood', 'fill-color', '--map-park'],
  ['water', 'fill-color', '--map-water'],
  ['building', 'fill-color', '--map-building'],
  ['building', 'fill-outline-color', '--map-street'],
  ['highway_path', 'line-color', '--map-street'],
  ['highway_minor', 'line-color', '--map-street'],
  ['highway_major_casing', 'line-color', '--map-street'],
  ['highway_motorway_casing', 'line-color', '--map-street'],
  ['highway_motorway_bridge_casing', 'line-color', '--map-street'],
  ['tunnel_motorway_casing', 'line-color', '--map-street'],
];
// Served from public/ (scripts/copy-worker.mjs). When bundled, MapLibre cannot find the worker next to its module.
const WORKER_URL = '/maplibre-gl-worker.mjs';
// Bike lanes from OpenStreetMap (scripts/export_bike_lanes.py). Without the file, the map has no lane layer.
const BIKE_LANES_URL = '/ciclovias.geojson';
export const LANE_CLASSES = ['separated', 'painted', 'shared'] as const;
type LaneClass = (typeof LANE_CLASSES)[number];
const CIRCLE_STEPS = 64;
// Space around the start and the destination. On a phone the free area is small, so the camera zooms out more.
const FRAME_MARGIN_PX = 40;
const PHONE_FRAME_MARGIN_PX = 56;
const FRAME_MAX_ZOOM = 15;
const DOUBLE_CLICK_MS = 400;
const DOUBLE_CLICK_PX = 12;
// P(free dock) bands. Keep them equal to the legend in planner.tsx.
export const FREE_STEPS = [0.5, 0.8, 0.95];

// MapLibre opens the compact credit when it first fills it. On a phone, the open credit covers the top of the map,
// so it starts closed. The "i" button still opens it.
function startCreditClosed(m: maplibregl.Map) {
  const credit = m.getContainer().querySelector('.maplibregl-ctrl-attrib');
  if (!credit || !isPhone()) return;
  const close = () => {
    if (!credit.classList.contains('maplibregl-compact-show')) return false;
    credit.classList.remove('maplibregl-compact-show');
    return true;
  };
  if (close()) return;
  const observer = new MutationObserver(() => close() && observer.disconnect());
  observer.observe(credit, { attributes: true, attributeFilter: ['class'] });
}

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

// The pickup: an orange pin with the dock icon of the card in its white circle. Keep the icon paths equal to Dock in
// components/icons.tsx.
// The white border is 3.5px: 36px for 24 units is 1.5px for each unit. The border goes past the top of the box.
const PICKUP_PIN_SVG = `<svg viewBox="0 0 24 32" width="36" height="48" overflow="visible" aria-hidden="true">
  <path d="M12 1C6 1 1.5 5.6 1.5 11.3 1.5 19 12 31 12 31s10.5-12 10.5-19.7C22.5 5.6 18 1 12 1Z"
    fill="var(--start-and-pickup)" stroke="var(--paper)" stroke-width="2.33" />
  <circle cx="12" cy="11.3" r="7.6" fill="var(--paper)" />
  <svg x="6.6" y="5.9" width="10.8" height="10.8" viewBox="0 0 24 24" fill="none" stroke="#000"
    stroke-width="2">
    <path d="M2.5 20.5V6L6 3.5v17Z" stroke-linejoin="round" />
    <path d="M7.6 12.3A3.8 3.8 0 1 1 7.6 19.7" />
    <circle cx="19.6" cy="16" r="3.5" />
    <path d="M8.5 16 11 9M10 8.5h3M10.7 11.5 15 16h4.6M15 16l1.8-6.5M15.6 9.5h2.7" stroke-linecap="round"
      stroke-linejoin="round" />
  </svg>
</svg>`;

// A pin marker over the map. It must not take the clicks for the stations under it (see .map-pin in globals.css).
function pinMarker(svg: string) {
  const el = document.createElement('div');
  el.className = 'map-pin';
  el.innerHTML = svg;
  return new maplibregl.Marker({ element: el, anchor: 'bottom' });
}

const collection = (features: GeoJSON.Feature[]): GeoJSON.FeatureCollection => ({ type: 'FeatureCollection', features });
const point = (p: Point, properties: Record<string, unknown> = {}): GeoJSON.Feature => ({
  type: 'Feature',
  properties,
  geometry: { type: 'Point', coordinates: [p.lng, p.lat] },
});

/** Station names come from the Ecobici feed. Escape them before they go into popup HTML. */
const esc = (v: unknown) =>
  String(v ?? '—').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);

function stationPopup(s: Station, t: Messages, c?: Candidate) {
  const lines = [
    `<b>${esc(s.name)}</b>`,
    `${esc(t.stationState[s.state] ?? s.state)} · ${t.map.docksOf(esc(s.docks), esc(s.capacity), esc(s.bikes))}`,
  ];
  if (c && c.p_free != null) lines.push(`${t.map.freeOnArrival}: <b>${pct(c.p_free)}</b>`);
  else if (s.p_full) lines.push(`${t.map.fullIn}: ${pct(s.p_full['15'])} / ${pct(s.p_full['30'])} / ${pct(s.p_full['45'])}`);
  else lines.push(t.map.noForecast);
  if (!c && s.p_empty?.['15'] != null) lines.push(`${t.map.emptyIn15}: ${pct(s.p_empty['15'])}`);
  return lines.join('<br/>');
}

// The style labels places with `name_en` ("Mexico City"). Use the label in the interface language, then the local name.
function labelField(lang: Lang): maplibregl.ExpressionSpecification {
  return ['coalesce', ['get', `name:${lang}`], ['get', 'name']];
}

function relabel(m: maplibregl.Map, lang: Lang) {
  for (const layer of m.getStyle().layers) {
    if (layer.type !== 'symbol') continue;
    const field = m.getLayoutProperty(layer.id, 'text-field');
    if (JSON.stringify(field ?? '').includes('"name')) m.setLayoutProperty(layer.id, 'text-field', labelField(lang));
  }
}

// Under every other layer. Painted and shared lanes show from closer zooms, so the city view stays clean.
function addBikeLanes(m: maplibregl.Map, color: (cls: LaneClass) => string) {
  m.addSource('bike-lanes', { type: 'geojson', data: BIKE_LANES_URL });
  const width = (far: number, near: number): maplibregl.ExpressionSpecification => ['interpolate', ['linear'], ['zoom'], 11, far, 16, near];
  const byClass = (cls: LaneClass): maplibregl.FilterSpecification => ['==', ['get', 'class'], cls];
  const layout: maplibregl.LineLayerSpecification['layout'] = { 'line-cap': 'round', 'line-join': 'round' };
  m.addLayer({ id: 'lanes-shared', type: 'line', source: 'bike-lanes', filter: byClass('shared'), minzoom: 13, layout, paint: { 'line-color': color('shared'), 'line-width': width(1.2, 3), 'line-dasharray': [0.1, 2] } });
  m.addLayer({ id: 'lanes-painted', type: 'line', source: 'bike-lanes', filter: byClass('painted'), minzoom: 12, layout, paint: { 'line-color': color('painted'), 'line-width': width(1.2, 3.5) } });
  m.addLayer({ id: 'lanes-separated', type: 'line', source: 'bike-lanes', filter: byClass('separated'), layout, paint: { 'line-color': color('separated'), 'line-width': width(1.8, 5) } });
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
  lang,
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
  lang: Lang;
}) {
  const t = MESSAGES[lang];
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const goalPin = useRef<maplibregl.Marker | null>(null);
  const pickupPin = useRef<maplibregl.Marker | null>(null);
  const credit = useRef<maplibregl.AttributionControl | null>(null);
  const pickGoal = useRef(onPickGoal);
  const select = useRef(onSelect);
  const langNow = useRef(lang);
  const lookup = useRef<{ stations: Map<string, Station>; candidates: Map<string, Candidate> }>({ stations: new Map(), candidates: new Map() });
  const [broken, setBroken] = useState(false);
  // The layers exist only after the style loads. An earlier draw waits here.
  const ready = useRef(false);
  const pending = useRef<(() => void) | null>(null);
  pickGoal.current = onPickGoal;
  select.current = onSelect;
  langNow.current = lang;
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
    credit.current = new maplibregl.AttributionControl({ compact: true, customAttribution: t.map.routesCredit });
    m.addControl(credit.current, 'top-left');
    startCreditClosed(m);
    m.on('load', () => {
      for (const [layer, property, cssVar] of BASEMAP_PAINT) if (m.getLayer(layer)) m.setPaintProperty(layer, property, v(cssVar));
      relabel(m, langNow.current);
      for (const id of ['stations', 'radius', 'walk', 'bike', 'candidates', 'start']) m.addSource(id, { type: 'geojson', data: collection([]) });
      addBikeLanes(m, (cls) => v(`--bike-lane-${cls}`));
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
      m.addLayer({ id: 'start-halo', type: 'circle', source: 'start', paint: { 'circle-radius': 20, 'circle-color': startAndPickup, 'circle-opacity': 0.22 } });
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
        if (s) popup.setLngLat([s.lng, s.lat]).setHTML(stationPopup(s, MESSAGES[langNow.current], c)).addTo(m);
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
      pickupPin.current = null;
      credit.current = null;
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
        goalPin.current ??= pinMarker(GOAL_PIN_SVG);
        goalPin.current.setLngLat([goal.lng, goal.lat]).addTo(m);
      } else {
        goalPin.current?.remove();
      }
      // At the start station, the start dot already marks the pickup.
      if (pickup && start && (pickup.lat !== start.lat || pickup.lng !== start.lng)) {
        pickupPin.current ??= pinMarker(PICKUP_PIN_SVG);
        pickupPin.current.setLngLat([pickup.lng, pickup.lat]).addTo(m);
      } else {
        pickupPin.current?.remove();
      }
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
    const m = map.current;
    if (!m || !credit.current) return;
    if (ready.current) relabel(m, lang);
    m.removeControl(credit.current);
    credit.current = new maplibregl.AttributionControl({ compact: true, customAttribution: t.map.routesCredit });
    m.addControl(credit.current, 'top-left');
    startCreditClosed(m);
  }, [lang]);

  useEffect(() => {
    map.current?.setPadding(inset);
  }, [inset.top, inset.bottom, inset.left, inset.right]);

  // Frame the trip when its ends change, and again when the panels over the map change size: the trip stays in the
  // middle of the free area. The map padding already is the inset, and fitBounds adds its padding on top.
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const ends = [start, goal].filter(Boolean) as Point[];
    if (!ends.length) return;
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (ends.length === 1) {
      m.easeTo({ center: [ends[0].lng, ends[0].lat], zoom: Math.max(m.getZoom(), 14), padding: inset, duration: still ? 0 : 900, easing: easeOut() });
      return;
    }
    const b = new maplibregl.LngLatBounds();
    for (const p of ends) b.extend([p.lng, p.lat]);
    const margin = isPhone() ? PHONE_FRAME_MARGIN_PX : FRAME_MARGIN_PX;
    m.fitBounds(b, { padding: margin, maxZoom: FRAME_MAX_ZOOM, duration: still ? 0 : 900, easing: easeOut() });
  }, [start?.lat, start?.lng, goal?.lat, goal?.lng, inset.top, inset.bottom, inset.left, inset.right]);

  if (broken) return <p className="notice">{t.map.broken}</p>;
  return <div ref={box} className="stage__mapbox" role="application" aria-label={t.map.label} />;
}
