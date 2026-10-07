// Street routes to draw the trip, from the public FOSSGIS OSRM servers (routing.openstreetmap.de). No key, best
// effort, credit required. The trip coordinates go to that service. If a request fails, the leg is a straight line.
// Display only: the planner scores use their own walking and riding estimates.

import { useEffect, useState } from 'react';

const SERVERS = { walk: 'https://routing.openstreetmap.de/routed-foot', bike: 'https://routing.openstreetmap.de/routed-bike' };
const CACHE_KEY = 'ecobici-routes-v1';
const CACHE_MAX = 80;
const WAIT_MS = 300;

export type Mode = keyof typeof SERVERS;
export type LngLat = [number, number];
export type Leg = {
  mode: Mode;
  coords: LngLat[];
  /** Metres along the route, or the straight line when `routed` is false. */
  distance_m: number;
  duration_min: number | null;
  routed: boolean;
};
type Point = { lat: number; lng: number };

const memory = new Map<string, Omit<Leg, 'mode'>>();
let loaded = false;

// 5 decimals (~1 m), so a repeated trip uses the cache.
const key = (mode: Mode, a: Point, b: Point) => [mode, a.lng, a.lat, b.lng, b.lat].map((v) => (typeof v === 'number' ? v.toFixed(5) : v)).join(',');

function loadCache() {
  if (loaded) return;
  loaded = true;
  try {
    for (const [k, v] of JSON.parse(localStorage.getItem(CACHE_KEY) ?? '[]')) memory.set(k, v);
  } catch {
    // No localStorage: memory only.
  }
}

function saveCache() {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify([...memory.entries()].slice(-CACHE_MAX)));
  } catch {
    // Same as above.
  }
}

function straight(mode: Mode, a: Point, b: Point): Leg {
  const r = 6_371_000;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLng = ((b.lng - a.lng) * Math.PI) / 180;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos((a.lat * Math.PI) / 180) * Math.cos((b.lat * Math.PI) / 180) * Math.sin(dLng / 2) ** 2;
  return { mode, coords: [[a.lng, a.lat], [b.lng, b.lat]], distance_m: 2 * r * Math.asin(Math.sqrt(h)), duration_min: null, routed: false };
}

export async function route(mode: Mode, a: Point, b: Point, signal?: AbortSignal): Promise<Leg> {
  loadCache();
  const k = key(mode, a, b);
  const hit = memory.get(k);
  if (hit) return { mode, ...hit };
  try {
    const url = `${SERVERS[mode]}/route/v1/driving/${a.lng},${a.lat};${b.lng},${b.lat}?overview=full&geometries=geojson`;
    const res = await fetch(url, { signal });
    if (!res.ok) throw new Error(String(res.status));
    const body = await res.json();
    const r = body.routes?.[0];
    if (body.code !== 'Ok' || !r) throw new Error(body.code ?? 'no route');
    const leg = { coords: r.geometry.coordinates as LngLat[], distance_m: r.distance, duration_min: r.duration / 60, routed: true };
    memory.set(k, leg);
    saveCache();
    return { mode, ...leg };
  } catch (e) {
    if (signal?.aborted) throw e;
    return straight(mode, a, b);
  }
}

/** Walk to the pickup (if it is not the start), ride to the drop-off, walk to the destination. Straight lines at
 *  once; routes replace them when they arrive. */
export function useTripRoutes(start: Point | null, pickup: Point | null, dropoff: Point | null, goal: Point | null) {
  const [legs, setLegs] = useState<Leg[]>([]);
  const sig = [start, pickup, dropoff, goal].map((p) => (p ? `${p.lat},${p.lng}` : '-')).join('|');
  useEffect(() => {
    if (!start || !pickup || !dropoff || !goal) return setLegs([]);
    const plan: [Mode, Point, Point][] = [];
    if (start.lat !== pickup.lat || start.lng !== pickup.lng) plan.push(['walk', start, pickup]);
    plan.push(['bike', pickup, dropoff], ['walk', dropoff, goal]);
    setLegs(plan.map(([m, a, b]) => straight(m, a, b)));
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      Promise.all(plan.map(([m, a, b]) => route(m, a, b, ctrl.signal)))
        .then(setLegs)
        .catch(() => {});
    }, WAIT_MS);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [sig]);
  return legs;
}
