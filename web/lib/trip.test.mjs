import { test } from 'node:test';
import assert from 'node:assert/strict';
import { dueTrip, nextTrip } from './trip.ts';

const NOW = Date.parse('2026-10-07T18:00:00Z');
const MIN = 60_000;
const HOUR = 60 * MIN;
// A capture 30 min old and a 20-min trip: the arrival time is already past.
const plan = (planId = 'p', dropoffId = 'B') => ({
  shown: {
    plan_id: planId,
    dropoff_id: dropoffId,
    captured_at: new Date(NOW - 30 * MIN).toISOString(),
    arrive_at: new Date(NOW - 10 * MIN).toISOString(),
  },
  pickupName: 'A',
  dropoffName: dropoffId,
});

test('the question waits for the trip time from now, not from the capture', () => {
  const trip = nextTrip(null, plan(), NOW);
  assert.equal(dueTrip(NOW, trip), null);
  assert.equal(dueTrip(NOW + 20 * MIN, trip)?.dropoffName, 'B');
});

test('a refresh of the same plan keeps the ask time and the answer', () => {
  const first = { ...nextTrip(null, plan(), NOW), answered: true };
  const again = nextTrip(first, plan(), NOW + 5 * MIN);
  assert.equal(again.askAt, first.askAt);
  assert.equal(again.answered, true);
});

test('a new destination or drop-off starts again', () => {
  const first = { ...nextTrip(null, plan(), NOW), answered: true };
  assert.equal(nextTrip(first, plan('q'), NOW + 5 * MIN).answered, false);
  assert.equal(nextTrip(first, plan('p', 'C'), NOW + 5 * MIN).askAt, NOW + 25 * MIN);
});

test('the question stops after 12 hours or an answer', () => {
  const trip = nextTrip(null, plan(), NOW);
  assert.equal(dueTrip(trip.askAt + 12 * HOUR, trip), null);
  assert.equal(dueTrip(trip.askAt + HOUR, { ...trip, answered: true }), null);
  assert.equal(dueTrip(NOW, null), null);
});

test('skipWait asks at once, but not twice', () => {
  const trip = nextTrip(null, plan(), NOW);
  assert.equal(dueTrip(NOW, trip, true)?.dropoffName, 'B');
  assert.equal(dueTrip(NOW, { ...trip, answered: true }, true), null);
});
