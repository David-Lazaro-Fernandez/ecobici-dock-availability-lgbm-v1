// The last plan, kept in this browser to ask about the trip after the arrival. Without localStorage (private mode),
// the page does not ask.

import type { Trip } from '@/lib/feedback';

const TRIP_KEY = 'ecobici-trip-v1';
// Ask about the trip from the arrival at the drop-off until this time after it.
const ASK_FOR_MS = 12 * 60 * 60_000;

function read(): Trip | null {
  try {
    return JSON.parse(localStorage.getItem(TRIP_KEY) ?? 'null') as Trip | null;
  } catch {
    return null;
  }
}

function write(trip: Trip) {
  try {
    localStorage.setItem(TRIP_KEY, JSON.stringify(trip));
  } catch {
    // No localStorage: see the top of the file.
  }
}

/** Keep the plan for the trip question. The same plan and drop-off keep their ask time and answer. */
export function saveTrip(trip: Omit<Trip, 'askAt' | 'answered'>, now = Date.now()) {
  write(nextTrip(read(), trip, now));
}

export function nextTrip(old: Trip | null, trip: Omit<Trip, 'askAt' | 'answered'>, now: number): Trip {
  const same = old?.shown.plan_id === trip.shown.plan_id && old.shown.dropoff_id === trip.shown.dropoff_id;
  if (same) return { ...trip, askAt: old.askAt, answered: old.answered };
  // The capture can be minutes old, so `arrive_at` can be in the past. Count the trip time from now.
  const tripMs = new Date(trip.shown.arrive_at).getTime() - new Date(trip.shown.captured_at).getTime();
  return { ...trip, askAt: now + tripMs, answered: false };
}

export function markAnswered() {
  const trip = read();
  if (trip) write({ ...trip, answered: true });
}

/** The trip to ask about at `now` (ms), or null. With `skipWait`, any trip without an answer. */
export function dueTrip(now: number, trip: Trip | null = read(), skipWait = false): Trip | null {
  if (!trip?.askAt || trip.answered) return null;
  if (skipWait) return trip;
  return now >= trip.askAt && now < trip.askAt + ASK_FOR_MS ? trip : null;
}
