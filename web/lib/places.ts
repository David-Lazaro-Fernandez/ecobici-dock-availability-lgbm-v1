// Place search, adapted from a-donde-ir. Local and instant: the Ecobici stations and the index of public/lugares.json
// (scripts/export_places.py). Online: Photon (OpenStreetMap, no key) in a box around the stations; the typed text goes
// to photon.komoot.io. Photon answers stay in localStorage, and a longer query reuses the answer of its prefix at once.

import type { Station } from '@/lib/api';

const PLACES_URL = '/lugares.json';
const GEOCODER = 'https://photon.komoot.io/api/';
const CACHE_KEY = 'ecobici-geocode-v1';
const CACHE_MAX = 60;
const MARGIN_DEG = 0.02;
// Ecobici stations come before every kind in the index.
const STATION_RANK = -1;

export type Suggestion = { lat: number; lng: number; name: string; context: string; stationId?: string };
type Place = Suggestion & { rank: number; plain: string; words: string[] };
export type PlacesFile = { version: number; kinds: string[]; places: [string, number, number, number][] };

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

// So that "roma" also starts "Colonia Roma Norte".
const LEADING = /^(colonia|col|barrio|estacion) /;

function makePlace(s: Suggestion, rank: number): Place {
  const p = plain(s.name);
  return { ...s, rank, plain: p.replace(LEADING, ''), words: p.split(' ') };
}

let placesFile: Promise<PlacesFile | null> | null = null;

/** The index file, fetched once. Null if it is missing: the search then uses stations and Photon only. */
export function loadPlaces() {
  placesFile ??= fetch(PLACES_URL)
    .then((r) => (r.ok ? (r.json() as Promise<PlacesFile>) : null))
    .catch(() => null);
  return placesFile;
}

export type IndexLabels = { station: (code: string) => string; kind: (kind: string) => string };
const SPANISH_LABELS: IndexLabels = { station: (code) => `Estación Ecobici ${code}`, kind: (kind) => kind };

/** `labels` sets the context line of each place. The kinds in lugares.json are in Spanish. */
export function buildIndex(file: PlacesFile | null, stations: Station[], labels: IndexLabels = SPANISH_LABELS): Place[] {
  const out: Place[] = stations.map((s) =>
    makePlace(
      { lat: s.lat, lng: s.lng, name: s.name.replace(/^CE-\d+\s*/, ''), context: labels.station(s.code), stationId: s.id },
      STATION_RANK,
    ),
  );
  for (const [name, kind, lat, lng] of file?.places ?? []) out.push(makePlace({ lat, lng, name, context: labels.kind(file!.kinds[kind]) }, kind));
  return out;
}

const km = (a: { lat: number; lng: number }, b: { lat: number; lng: number }) =>
  Math.hypot(a.lat - b.lat, (a.lng - b.lng) * Math.cos((a.lat * Math.PI) / 180)) * 111.32;

/** Places where each typed word starts a word of the name. Order: same start, kind, distance to `near`, shorter
 *  name. */
export function searchPlaces(index: Place[], query: string, near: { lat: number; lng: number }, limit: number): Suggestion[] {
  const q = plain(query);
  if (!q) return [];
  const tokens = q.split(' ');
  const hits: { place: Place; score: number; km: number }[] = [];
  for (const place of index) {
    if (!tokens.every((t) => place.words.some((w) => w.startsWith(t)))) continue;
    hits.push({ place, score: place.plain.startsWith(q) ? 0 : 1, km: km(near, place) });
  }
  hits.sort((a, b) => a.score - b.score || a.place.rank - b.place.rank || a.km - b.km || a.place.name.length - b.place.name.length);
  const seen = new Set<string>();
  const out: Suggestion[] = [];
  for (const { place } of hits) {
    const key = `${place.plain}|${place.context}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const { rank, plain: _, words, ...s } = place;
    out.push(s);
    if (out.length >= limit) break;
  }
  return out;
}

/** Local results first, unless the text has a number (a street address): then Photon first. No repeated names. */
export function merge(query: string, local: Suggestion[], online: Suggestion[], limit: number) {
  const ordered = /\d/.test(query) ? [...online, ...local] : [...local, ...online];
  const seen = new Set<string>();
  return ordered.filter((s) => !seen.has(plain(s.name)) && seen.add(plain(s.name))).slice(0, limit);
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
    // No localStorage (private mode): keep the cache in memory.
  }
}

function saveCache() {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify([...remote.entries()].slice(-CACHE_MAX)));
  } catch {
    // Same as above.
  }
}

/** Saved Photon answers for the longest saved query that starts `query`, filtered by `query`. No network. */
export function cachedOnline(query: string, near: { lat: number; lng: number }, limit: number): Suggestion[] {
  loadCache();
  const q = plain(query);
  let best = '';
  for (const k of remote.keys()) if (q.startsWith(k) && k.length > best.length) best = k;
  if (!best) return [];
  return searchPlaces(remote.get(best)!.map((s) => makePlace(s, 0)), query, near, limit);
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
