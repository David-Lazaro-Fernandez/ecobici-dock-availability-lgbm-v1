// Client for ecobici.api (src/ecobici/api.py), adapted from the a-donde-ir useApi. NEXT_PUBLIC_API_URL sets the
// address at build time. CACHE_MS is 1 min because captures arrive every 2 min.

import { useEffect, useState } from 'react';

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const WAIT_MS = 250;
const CACHE_MS = 60_000;
const CACHE_MAX = 50;

export type State = 'available' | 'full' | 'unavailable' | 'stale';

export type Station = {
  id: string;
  code: string;
  name: string;
  lat: number;
  lng: number;
  capacity: number | null;
  docks: number | null;
  bikes: number | null;
  state: State;
  /** P(full) at 15, 30 and 45 min, keyed by minutes. Null if not predicted. */
  p_full: Record<string, number> | null;
  /** P(no bike) at 15 min, keyed by minutes. Null without the empty-station model. */
  p_empty: Record<string, number> | null;
};

export type StationsResponse = {
  captured_at: string;
  weather_missing: boolean;
  horizons: number[];
  stations: Station[];
};

export type Pickup = Station & {
  walk_m: number;
  walk_min: number;
  /** P(no bike left on arrival). 0 at the start station. */
  p_empty_at_arrival: number | null;
  /** Walk + P(no bike) × failure cost + expected minutes of the best drop-off. */
  total_min: number | null;
};

export type Candidate = Station & {
  /** 1 = best. Null if not recommendable (out of service or stale). */
  rank: number | null;
  recommendable: boolean;
  walk_m: number;
  walk_min: number;
  ride_min: number;
  ride_source: string;
  arrive_at: string;
  p_full_at_arrival: number | null;
  p_free: number | null;
  /** From the pickup: ride + walk + P(full) × failure cost. */
  expected_min: number | null;
  outside_horizons: boolean;
};

export type PlanResponse = {
  captured_at: string;
  weather_missing: boolean;
  radius_m: number;
  failure_min: number;
  pickup: Pickup;
  /** The compared pickups, lowest total first. */
  pickup_options: Pickup[];
  /** The start station asked for, if it had no bike to take. Then `pickup` is a station nearby. */
  requested: Station | null;
  candidates: Candidate[];
};

const cache = new Map<string, { at: number; data: unknown }>();

function problem(status: number, detail: unknown) {
  if (status === 503) return 'Todavía no hay datos en vivo. Intenta en un minuto.';
  if (status === 422 && detail === 'no station with a bike near the start') return 'No hay estaciones con bicis cerca del punto de partida.';
  if (status === 422) return 'No se pudo calcular el viaje con esos datos.';
  return 'El servicio de predicción no responde. ¿Está corriendo la API?';
}

function cached(url: string) {
  const hit = cache.get(url);
  return hit && Date.now() - hit.at < CACHE_MS ? hit.data : undefined;
}

async function load(url: string, signal: AbortSignal) {
  const hit = cached(url);
  if (hit !== undefined) return hit;
  const res = await fetch(url, { signal }).catch((e) => {
    throw signal.aborted ? e : new Error(problem(0, null));
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(problem(res.status, body?.detail));
  cache.delete(url);
  cache.set(url, { at: Date.now(), data: body });
  if (cache.size > CACHE_MAX) cache.delete(cache.keys().next().value!);
  return body;
}

/** Query `path` with `params`. If `params` is null, clear the state. A new `refresh` value skips the cache. While
 *  loading, `data` keeps the previous answer. */
export function useApi<T>(path: string, params: URLSearchParams | null, refresh: unknown = null, wait = WAIT_MS) {
  const query = params ? String(params) : '';
  const url = params ? `${API_URL}${path}${query ? `?${query}` : ''}` : null;
  const [state, setState] = useState<{ data: T | null; error: string; loading: boolean }>({
    data: null,
    error: '',
    loading: false,
  });
  useEffect(() => {
    if (!url) {
      setState({ data: null, error: '', loading: false });
      return;
    }
    const hit = cached(url);
    if (hit !== undefined && refresh === null) {
      setState({ data: hit as T, error: '', loading: false });
      return;
    }
    if (refresh !== null) cache.delete(url);
    setState((s) => ({ ...s, loading: true }));
    const ctrl = new AbortController();
    const timer = setTimeout(() => {
      load(url, ctrl.signal)
        .then((data) => setState({ data: data as T, error: '', loading: false }))
        .catch((e: Error) => {
          if (!ctrl.signal.aborted) setState((s) => ({ ...s, error: e.message, loading: false }));
        });
    }, wait);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [url, refresh, wait]);
  return state;
}
