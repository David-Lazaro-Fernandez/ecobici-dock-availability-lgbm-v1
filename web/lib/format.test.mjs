// npm test
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { pct, sharedNames, shortName } from './format.ts';

test('shortName drops the station code', () => assert.equal(shortName('CE-017 Reforma - Río Tiber'), 'Reforma - Río Tiber'));
test('sharedNames compares the names without the code', () => {
  const stations = [{ name: 'CE-112 Liverpool - Génova' }, { name: 'CE-113 Liverpool - Génova' }, { name: 'CE-114 Durango-Monterrey' }];
  assert.deepEqual([...sharedNames(stations)], ['Liverpool - Génova']);
});

test('pct never shows certainty', () => {
  assert.equal(pct(0.9994), '> 99 %');
  assert.equal(pct(1), '> 99 %');
  assert.equal(pct(0.0001), '< 1 %');
  assert.equal(pct(0), '< 1 %');
});
test('pct rounds the rest and marks a missing value', () => {
  assert.equal(pct(0.923), '92 %');
  assert.equal(pct(0.994), '99 %');
  assert.equal(pct(0.005), '1 %');
  assert.equal(pct(null), '—');
});
