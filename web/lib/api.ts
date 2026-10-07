// Client for ecobici.api (src/ecobici/api.py). NEXT_PUBLIC_API_URL sets the address at build time.
// Adapted from a-donde-ir's useApi: each query waits WAIT_MS after the last change and cancels the previous one;
// answers stay cached for CACHE_MS because captures arrive every 2 minutes.

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
  /** P(full) at 15 / 30 / 45 min, keyed by minutes. Null when the station is not predicted. */
  p_full: Record<string, number> | null;
};

export type StationsResponse = {
  captured_at: string;
  weather_missing: boolean;
  horizons: number[];
  stations: Station[];
};

export type Pickup = Station & { walk_m: number; walk_min: number };

export type Candidate = Station & {
  /** 1 = best. Null when not recommendable (out of service or stale). */
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
  /** The start station asked for, when it had no bike to take and the pickup moved to the nearest one that does. */
  requested: Station | null;
  candidates: Candidate[];
};

const cache = new Map<string, { at: number; data: unknown }>();

function problem(status: number, detail: unknown) {
  if (status === 422 && typeof detail === 'string') return detail;
  if (status === 503) return typeof detail === 'string' ? `No live data yet: ${detail}.` : 'No live data yet.';
  return 'The prediction service is not reachable. Is the API running?';
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

/** Query `path` with `params`. With `params` null, nothing is queried and the state clears. A change of `refresh`
 *  queries again (past the cache). While loading, `data` keeps the previous answer. */
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
