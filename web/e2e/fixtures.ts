// Fake API answers for the layout tests. The names are long and the plan shows every optional line, so the card
// has the most content that a real plan can have.

import type { Candidate, PlanResponse, Station, StationsResponse } from '@/lib/api';
import type { Trip } from '@/lib/feedback';

// The start station has no bike, so the plan moves the pickup and the card shows a warning.
export const START_NAME = 'Niños Héroes-Dr. Río de la Loza';
const PICKUP_NAME = 'Claudio Bernard-Dr. Liceaga';
export const DROPOFF_NAME = 'Acapulco-Puebla';

const DROPOFF_NAMES = [
  DROPOFF_NAME,
  'Av. Insurgentes Sur-Viaducto Presidente Miguel Alemán',
  'Liverpool - Génova',
  'Liverpool - Génova',
  'Durango-Monterrey',
  'Orizaba-Álvaro Obregón',
  'Colima-Córdoba',
  'Jalapa-Querétaro',
  'Tonalá-Chihuahua',
];
const OUT_OF_SERVICE = 'Puebla-Mérida';

const ORIGIN = { lat: 19.4206, lng: -99.1584 };
const MINUTE = 60_000;

export const codeOf = (index: number) => String(100 + index);

// As in the API: the name starts with "CE-<code>", and the page drops that prefix.
function station(index: number, name: string, overrides: Partial<Station> = {}): Station {
  return {
    id: `s${index}`,
    code: codeOf(index),
    name: `CE-${codeOf(index)} ${name}`,
    lat: ORIGIN.lat + index * 0.0009,
    lng: ORIGIN.lng + (index % 3) * 0.0011,
    capacity: 25,
    docks: 12,
    bikes: 6,
    state: 'available',
    p_full: { '15': 0.1, '30': 0.12, '45': 0.15 },
    p_empty: { '15': 0.05 },
    ...overrides,
  };
}

const pickupStation = station(0, PICKUP_NAME);
const requestedStation = station(1, START_NAME, { bikes: 0, docks: 25, state: 'available' });
const dropoffStations = DROPOFF_NAMES.map((name, i) => station(10 + i, name));
const outOfService = station(30, OUT_OF_SERVICE, { state: 'unavailable', docks: null, bikes: null, p_full: null });

export function stationsResponse(now = Date.now()): StationsResponse {
  return {
    captured_at: new Date(now).toISOString(),
    weather_missing: false,
    horizons: [15, 30, 45],
    stations: [pickupStation, requestedStation, ...dropoffStations, outOfService],
  };
}

/** A past trip without an answer: the dock asks about it on top of the trip ends. */
export function dueTrip(now = Date.now()): Trip {
  return {
    shown: {
      plan_id: 'past-plan',
      captured_at: new Date(now - 40 * MINUTE).toISOString(),
      pickup_id: pickupStation.id,
      dropoff_id: dropoffStations[1].id,
      rank: 2,
      arrive_at: new Date(now - 25 * MINUTE).toISOString(),
      p_free: 0.97,
      p_empty_at_arrival: 0.18,
    },
    pickupName: PICKUP_NAME,
    dropoffName: DROPOFF_NAMES[1],
    askAt: now - 25 * MINUTE,
    answered: false,
  };
}

const P_FREE_BY_RANK = [0.995, 0.97, 0.9, 0.86, 0.75, 0.62, 0.55, 0.4, 0.3];

export function planResponse(now = Date.now()): PlanResponse {
  const candidates: Candidate[] = dropoffStations.map((s, i) => ({
    ...s,
    rank: i + 1,
    recommendable: true,
    walk_m: 120 + i * 45,
    walk_min: 2 + i * 0.6,
    ride_min: 9 + i,
    ride_source: 'osrm',
    arrive_at: new Date(now + (12 + i) * MINUTE).toISOString(),
    p_full_at_arrival: 1 - P_FREE_BY_RANK[i],
    p_free: P_FREE_BY_RANK[i],
    expected_min: 14 + i,
    outside_horizons: false,
  }));
  const pickup = { ...pickupStation, walk_m: 430, walk_min: 6, p_empty_at_arrival: 0.18, total_min: 22 };
  return {
    captured_at: new Date(now).toISOString(),
    weather_missing: false,
    radius_m: 500,
    failure_min: 7.5,
    pickup,
    pickup_options: [pickup],
    requested: requestedStation,
    candidates: [
      ...candidates,
      {
        ...outOfService,
        rank: null,
        recommendable: false,
        walk_m: 600,
        walk_min: 8,
        ride_min: 15,
        ride_source: 'osrm',
        arrive_at: new Date(now + 20 * MINUTE).toISOString(),
        p_full_at_arrival: null,
        p_free: null,
        expected_min: null,
        outside_horizons: false,
      },
    ],
  };
}
