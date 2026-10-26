// Place search, adapted from a-donde-ir. Local and instant: the Ecobici stations, the index of public/lugares.json
// (scripts/export_places.py), the streets of public/calles.json and the house numbers of public/numeros.json
// (scripts/export_streets.py). Online: Photon (OpenStreetMap, no key) in a box around the stations; the typed text goes
// to photon.komoot.io. Photon answers stay in localStorage, and a longer query reuses the answer of its prefix at once.

import type { Station } from '@/lib/api';

const PLACES_URL = '/lugares.json';
const STREETS_URL = '/calles.json';
const NUMBERS_URL = '/numeros.json';
const GEOCODER = 'https://photon.komoot.io/api/';
const CACHE_KEY = 'ecobici-geocode-v2';
const CACHE_MAX = 60;
const MARGIN_DEG = 0.02;
// Ecobici stations come before every kind in the index.
const STATION_RANK = -1;

/** Where a suggestion comes from. An `address` has a house number, no name or is a street: the plan log keeps no name for it. */
export type Source = 'station' | 'index' | 'photon' | 'address';
/** `osm`: the OpenStreetMap id of a Photon place, as N123, W123 or R123. */
export type Suggestion = { lat: number; lng: number; name: string; context: string; source: Source; stationId?: string; osm?: string };
type Place = Suggestion & { rank: number; plain: string; words: string[]; kindWords: string[] };
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

// People type the kind with the name: "metro doctores", "estación ecobici reforma". The index name has no kind.
const STATION_KIND_WORDS = ['ecobici', 'estacion'];
const TRANSIT_KIND_WORDS: Record<string, string[]> = { Metro: ['estacion'], Metrobús: ['mb', 'estacion'], 'Tren ligero': ['estacion'] };
const kindWordsOf = (kind: string) => [...plain(kind).split(' '), ...(TRANSIT_KIND_WORDS[kind] ?? [])];

function makePlace(s: Suggestion, rank: number, kindWords: string[] = []): Place {
  const p = plain(s.name);
  return { ...s, rank, plain: p.replace(LEADING, ''), words: p.split(' '), kindWords };
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
      { lat: s.lat, lng: s.lng, name: s.name.replace(/^CE-\d+\s*/, ''), context: labels.station(s.code), source: 'station', stationId: s.id },
      STATION_RANK,
      STATION_KIND_WORDS,
    ),
  );
  const kindWords = file?.kinds.map(kindWordsOf) ?? [];
  for (const [name, kind, lat, lng] of file?.places ?? [])
    out.push(makePlace({ lat, lng, name, context: labels.kind(file!.kinds[kind]), source: 'index' }, kind, kindWords[kind]));
  return out;
}

const km = (a: { lat: number; lng: number }, b: { lat: number; lng: number }) =>
  Math.hypot(a.lat - b.lat, (a.lng - b.lng) * Math.cos((a.lat * Math.PI) / 180)) * 111.32;

export type StreetsFile = { version: number; boroughs: string[]; streets: [string, number, number[]][] };
type Street = { name: string; words: string[]; borough: string; points: number[] };

let streetsFile: Promise<StreetsFile | null> | null = null;

/** The street file, fetched once. Null if it is missing: the search then has no street suggestions. */
export function loadStreets() {
  streetsFile ??= fetch(STREETS_URL)
    .then((r) => (r.ok ? (r.json() as Promise<StreetsFile>) : null))
    .catch(() => null);
  return streetsFile;
}

export function buildStreets(file: StreetsFile | null): Street[] {
  return (file?.streets ?? []).map(([name, borough, points]) => ({
    name,
    words: plain(name).split(' '),
    borough: file!.boroughs[borough],
    points,
  }));
}

/** The point of the street nearest to `near`. `points` is a flat list: lat, lng, lat, lng, … */
function nearestPoint(points: number[], near: { lat: number; lng: number }) {
  let best = { lat: points[0], lng: points[1], km: Infinity };
  for (let i = 0; i < points.length; i += 2) {
    const d = km(near, { lat: points[i], lng: points[i + 1] });
    if (d < best.km) best = { lat: points[i], lng: points[i + 1], km: d };
  }
  return best;
}

const ALL_DIGITS = /^\d+$/;
const HOUSE_NUMBER = /^\d+[a-z]?$/;

const startsEachWord = (words: string[], tokens: string[]) => tokens.every((t) => words.some((w) => w.startsWith(t)));

/** Streets where each typed word starts a word of the name, nearest to `near` first. A house number at the end is
 *  dropped when no street has it in the name ("durango 49" gives "Calle Durango"). */
export function searchStreets(streets: Street[], query: string, near: { lat: number; lng: number }, limit: number): Suggestion[] {
  const tokens = plain(query).split(' ');
  const matching = (words: string[]) => streets.filter((s) => startsEachWord(s.words, words));
  let found = matching(tokens);
  if (!found.length && tokens.length > 1 && ALL_DIGITS.test(tokens[tokens.length - 1])) found = matching(tokens.slice(0, -1));
  return found
    .map((street) => ({ street, ...nearestPoint(street.points, near) }))
    .sort((a, b) => a.km - b.km || a.street.name.length - b.street.name.length)
    .slice(0, limit)
    .map(({ street, lat, lng }) => ({ lat, lng, name: street.name, context: street.borough, source: 'address' }));
}

/** A block: start lat, start lng, end lat, end lng, and [hundred, place of hundred*100, place of hundred*100+99] with
 *  the places from 0 at the start to 100 at the end. */
type Block = [number, number, number, number, [number, number, number][]];
/** `streets` of numeros.json: each record is [number, lat, lng, neighbourhood index]. */
export type NumbersFile = {
  version: number;
  boroughs: string[];
  neighbourhoods: string[];
  streets: [string, number, [string, number, number, number][], Block[]?][];
};
type NumberedStreet = {
  name: string;
  words: string[];
  borough: string;
  records: [string, number, number, number][];
  blocks: Block[];
};
export type Addresses = { streets: NumberedStreet[]; neighbourhoods: string[] };

let numbersFile: Promise<NumbersFile | null> | null = null;

/** The house-number file (about 3.4 MB, 0.9 MB compressed), fetched once, on the first text with a digit. Null if it is missing. */
export function loadNumbers() {
  numbersFile ??= fetch(NUMBERS_URL)
    .then((r) => (r.ok ? (r.json() as Promise<NumbersFile>) : null))
    .catch(() => null);
  return numbersFile;
}

export function buildAddresses(file: NumbersFile | null): Addresses {
  const streets = (file?.streets ?? []).map(([name, borough, records, blocks]) => ({
    name,
    words: plain(name).split(' '),
    borough: file!.boroughs[borough],
    records,
    blocks: blocks ?? [],
  }));
  return { streets, neighbourhoods: file?.neighbourhoods ?? [] };
}

type NumberRecord = NumberedStreet['records'][number];

// Two known numbers of the same side farther apart than this say nothing about a number between them: the
// street may have two parts with the same name.
const MAX_SPAN_M = 500;

const numberValue = (record: NumberRecord) => parseInt(record[0], 10);

/** A point for a house number that is not in the file: between the nearest known numbers of the same side (same
 *  parity) below and above it. Null if one side has no known number or the two are `MAX_SPAN_M` apart or more. */
export function estimatePoint(records: NumberRecord[], number: number) {
  let below: NumberRecord | null = null;
  let above: NumberRecord | null = null;
  for (const record of records) {
    const value = numberValue(record);
    if (value % 2 !== number % 2) continue;
    if (value < number && (!below || value > numberValue(below))) below = record;
    if (value > number && (!above || value < numberValue(above))) above = record;
  }
  if (!below || !above) return null;
  const from = { lat: below[1], lng: below[2] };
  const to = { lat: above[1], lng: above[2] };
  if (km(from, to) * 1000 >= MAX_SPAN_M) return null;
  const t = (number - numberValue(below)) / (numberValue(above) - numberValue(below));
  return { lat: from.lat + (to.lat - from.lat) * t, lng: from.lng + (to.lng - from.lng) * t, neighbourhood: below[3] };
}

const HUNDRED = 100;

/** A point for a house number in a block of the street: the block where the hundred of the number has known numbers.
 *  With more than one block for the hundred, the nearest to `near`. Null if no block has the hundred. */
export function estimateInBlock(blocks: Block[], number: number, near: { lat: number; lng: number }) {
  const hundred = Math.floor(number / HUNDRED);
  const candidates = blocks.flatMap((block) => {
    const places = block[4].find(([h]) => h === hundred);
    if (!places) return [];
    const [startLat, startLng, endLat, endLng] = block;
    const t = (places[1] + ((number - hundred * HUNDRED) / (HUNDRED - 1)) * (places[2] - places[1])) / 100;
    const middle = { lat: (startLat + endLat) / 2, lng: (startLng + endLng) / 2 };
    return [{ lat: startLat + (endLat - startLat) * t, lng: startLng + (endLng - startLng) * t, away: km(near, middle) }];
  });
  return candidates.sort((a, b) => a.away - b.away)[0] ?? null;
}

/** Addresses for a text like "durango 49" or "durango 49a": the street words, then the house number. Nearest to
 *  `near` first. A number that is in the file gives its point. A number that no street has gives an
 *  estimate with `approximate` in the context: between its neighbours, or else in the block of its hundred. Empty if
 *  the text has no house number. */
export function searchAddresses(addresses: Addresses, query: string, near: { lat: number; lng: number }, limit: number, approximate = 'aprox.'): Suggestion[] {
  const tokens = plain(query).split(' ');
  const number = tokens.pop() ?? '';
  if (!tokens.length || !HOUSE_NUMBER.test(number)) return [];
  const found: { suggestion: Suggestion; km: number }[] = [];
  const add = (street: NumberedStreet, name: string, lat: number, lng: number, neighbourhood: number | null, note?: string) => {
    const context = [neighbourhood === null ? '' : addresses.neighbourhoods[neighbourhood], street.borough].filter(Boolean).join(', ');
    found.push({ suggestion: { lat, lng, name, context: note ? `${context} · ${note}` : context, source: 'address' }, km: km(near, { lat, lng }) });
  };
  const matching = addresses.streets.filter((street) => startsEachWord(street.words, tokens));
  for (const street of matching) {
    for (const [recordNumber, lat, lng, neighbourhood] of street.records.filter((r) => r[0].toLowerCase() === number))
      add(street, `${street.name} ${recordNumber}`, lat, lng, neighbourhood);
  }
  // An estimate is for a number that no street has: next to an exact address, it would be noise.
  if (!found.length && ALL_DIGITS.test(number)) {
    const value = parseInt(number, 10);
    for (const street of matching) {
      const point = estimatePoint(street.records, value) ?? estimateInBlock(street.blocks, value, near);
      if (point) add(street, `${street.name} ${number}`, point.lat, point.lng, 'neighbourhood' in point ? point.neighbourhood : null, approximate);
    }
  }
  return found.sort((a, b) => a.km - b.km).slice(0, limit).map((f) => f.suggestion);
}

/** Places where each typed word starts a word of the name or is a word of the kind ("metro"). One word at least
 *  must match the name. Order: kind typed, same start, kind, distance to `near`, shorter name. */
export function searchPlaces(index: Place[], query: string, near: { lat: number; lng: number }, limit: number): Suggestion[] {
  const q = plain(query);
  if (!q) return [];
  const tokens = q.split(' ');
  const hits: { place: Place; nameOnly: number; score: number; km: number }[] = [];
  for (const place of index) {
    const inName = tokens.filter((t) => place.words.some((w) => w.startsWith(t)));
    if (!inName.length || !tokens.every((t) => inName.includes(t) || place.kindWords.includes(t))) continue;
    const nameOnly = inName.length === tokens.length ? 1 : 0;
    hits.push({ place, nameOnly, score: place.plain.startsWith(inName.join(' ')) ? 0 : 1, km: km(near, place) });
  }
  hits.sort(
    (a, b) =>
      a.nameOnly - b.nameOnly || a.score - b.score || a.place.rank - b.place.rank || a.km - b.km || a.place.name.length - b.place.name.length,
  );
  const seen = new Set<string>();
  const out: Suggestion[] = [];
  for (const { place } of hits) {
    const key = `${place.plain}|${place.context}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const { rank, plain: _, words, kindWords, ...s } = place;
    out.push(s);
    if (out.length >= limit) break;
  }
  return out;
}

/** Local results first, unless the text has a number (a street address): then Photon first. No repeated names,
 *  except Ecobici stations: two stations can have the same name, and each one is a different place. */
export function merge(query: string, local: Suggestion[], online: Suggestion[], limit: number) {
  const ordered = /\d/.test(query) ? [...online, ...local] : [...local, ...online];
  const seen = new Set<string>();
  const fresh = (s: Suggestion) => {
    const name = plain(s.name);
    const id = s.stationId && `station:${s.stationId}`;
    if (id ? seen.has(id) : seen.has(name)) return false;
    seen.add(name);
    if (id) seen.add(id);
    return true;
  };
  return ordered.filter(fresh).slice(0, limit);
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
  const address = Boolean(p.housenumber) || !p.name;
  const osm = p.osm_type && p.osm_id ? `${p.osm_type}${p.osm_id}` : undefined;
  return { lat: f.geometry.coordinates[1], lng: f.geometry.coordinates[0], name: p.name ?? street, context, source: address ? 'address' : 'photon', osm };
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
