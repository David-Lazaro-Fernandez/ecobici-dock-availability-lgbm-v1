// Place search for the start and destination inputs. Ecobici stations match locally and instantly; addresses come
// from Photon (OpenStreetMap, no key; same geocoder as a-donde-ir), limited to a box around the stations and cached
// in localStorage. Typed text goes to photon.komoot.io.

import type { Station } from '@/lib/api';

const GEOCODER = 'https://photon.komoot.io/api/';
const CACHE_KEY = 'ecobici-geocode-v1';
const CACHE_MAX = 60;
const MARGIN_DEG = 0.02;

export type Suggestion = { lat: number; lng: number; name: string; context: string; stationId?: string };

/** Lowercase, no accents or punctuation: "Álvaro Obregón" → "alvaro obregon". */
export function plain(text: string) {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9ñ\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Stations whose code or name has every typed word as a word start ("ref flor" → "Reforma- Florencia"). */
export function searchStations(stations: Station[], query: string, limit: number): Suggestion[] {
  const tokens = plain(query).split(' ').filter(Boolean);
  if (!tokens.length) return [];
  const out: Suggestion[] = [];
  for (const s of stations) {
    const words = plain(`${s.code} ${s.name.replace(/^CE-\d+\s*/, '')}`).split(' ');
    if (tokens.every((t) => words.some((w) => w.startsWith(t)))) {
      out.push({ lat: s.lat, lng: s.lng, name: s.name, context: `Ecobici station ${s.code}`, stationId: s.id });
      if (out.length >= limit) break;
    }
  }
  return out;
}

/** Photon's bbox (minLon,minLat,maxLon,maxLat) around the stations. */
export function bbox(stations: Station[]) {
  if (!stations.length) return '';
  const lats = stations.map((s) => s.lat);
  const lngs = stations.map((s) => s.lng);
  return [Math.min(...lngs) - MARGIN_DEG, Math.min(...lats) - MARGIN_DEG, Math.max(...lngs) + MARGIN_DEG, Math.max(...lats) + MARGIN_DEG].join(',');
}

type PhotonFeature = { geometry: { coordinates: [number, number] }; properties: Record<string, string | undefined> };

function toSuggestion(f: PhotonFeature): Suggestion {
  const p = f.properties;
  const street = [p.street, p.housenumber].filter(Boolean).join(' ');
  const context = [street, p.district ?? p.locality, p.city ?? p.county]
    .filter((v, i, all) => v && v !== p.name && all.indexOf(v) === i)
    .join(', ');
  return { lat: f.geometry.coordinates[1], lng: f.geometry.coordinates[0], name: p.name ?? street, context };
}

const remote = new Map<string, Suggestion[]>();
let loaded = false;

function loadCache() {
  if (loaded) return;
  loaded = true;
  try {
    for (const [k, v] of JSON.parse(localStorage.getItem(CACHE_KEY) ?? '[]') as [string, Suggestion[]][]) remote.set(k, v);
  } catch {
    // No localStorage (private mode or blocked): the cache stays in memory.
  }
}

function saveCache() {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify([...remote.entries()].slice(-CACHE_MAX)));
  } catch {
    // Same as above.
  }
}

/** Addresses and places for `query` near `near`, inside `box`. */
export async function geocode(query: string, near: { lat: number; lng: number }, box: string, limit: number, signal?: AbortSignal) {
  loadCache();
  const key = plain(query);
  const hit = remote.get(key);
  if (hit) return hit;
  // Photon rejects lang=es; lang=default returns local names.
  const params = new URLSearchParams({ q: query, limit: String(limit), lang: 'default', lat: String(near.lat), lon: String(near.lng) });
  if (box) params.set('bbox', box);
  const res = await fetch(`${GEOCODER}?${params}`, { signal });
  if (!res.ok) throw new Error(String(res.status));
  const data: { features: PhotonFeature[] } = await res.json();
  const out = data.features.map(toSuggestion).filter((s) => s.name);
  remote.set(key, out);
  saveCache();
  return out;
}
