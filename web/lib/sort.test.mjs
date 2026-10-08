// npm test
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { sortCandidates } from './sort.ts';

const c = (id, { walk_m, p_free, expected_min, recommendable = true }) => ({ id, walk_m, p_free, expected_min, recommendable });
const list = [
  c('near-risky', { walk_m: 50, p_free: 0.4, expected_min: 18 }),
  c('fast', { walk_m: 300, p_free: 0.95, expected_min: 12 }),
  c('sure', { walk_m: 450, p_free: 1.0, expected_min: 14 }),
  c('broken', { walk_m: 10, p_free: null, expected_min: null, recommendable: false }),
];
const ids = (key) => sortCandidates(list, key).map((x) => x.id);

test('time follows the expected trip time', () => assert.deepEqual(ids('time'), ['fast', 'sure', 'near-risky', 'broken']));
test('walk puts the nearest first', () => assert.deepEqual(ids('walk'), ['near-risky', 'fast', 'sure', 'broken']));
test('free puts the likeliest free dock first', () => assert.deepEqual(ids('free'), ['sure', 'fast', 'near-risky', 'broken']));
test('stations that cannot be recommended always go last', () => {
  for (const key of ['time', 'walk', 'free']) assert.equal(ids(key).at(-1), 'broken');
});
test('does not reorder the input', () => {
  const before = list.map((x) => x.id);
  sortCandidates(list, 'walk');
  assert.deepEqual(list.map((x) => x.id), before);
});
