// npm test
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildIndex, merge, plain, searchPlaces } from './places.ts';

const file = {
  version: 1,
  kinds: ['Colonia', 'Metro', 'Edificio'],
  places: [
    ['Torre Reforma Latino', 2, 19.4253, -99.1625],
    ['Colonia Roma Norte', 0, 19.418, -99.16],
    ['Reforma', 1, 19.43, -99.15],
    ['Ángel del Pedregal', 2, 19.3, -99.2],
  ],
};
const stations = [{ id: '7', code: '017', name: 'CE-017 Reforma - Río Tiber', lat: 19.428, lng: -99.168 }];
const index = buildIndex(file, stations);
const near = { lat: 19.42, lng: -99.16 };
const names = (q) => searchPlaces(index, q, near, 5).map((s) => s.name);

test('a landmark from the index matches at once', () => assert.deepEqual(names('torre reforma lat'), ['Torre Reforma Latino']));
test('each typed word must start a word of the name', () => assert.deepEqual(names('ref lat'), ['Torre Reforma Latino']));
test('"Colonia" is skipped for the start match', () => assert.equal(names('roma')[0], 'Colonia Roma Norte'));
test('accents do not matter', () => assert.deepEqual(names('angel'), ['Ángel del Pedregal']));
test('Ecobici stations come before the other kinds', () => {
  const got = searchPlaces(index, 'reforma', near, 5);
  assert.equal(got[0].stationId, '7');
  assert.equal(got[0].context, 'Estación Ecobici 017');
});
test('plain removes accents and punctuation', () => assert.equal(plain('Álvaro Obregón, CDMX!'), 'alvaro obregon cdmx'));
test('merge puts local first, online first for a street number, and drops repeated names', () => {
  const local = [{ name: 'Reforma 222' }, { name: 'Roma' }];
  const online = [{ name: 'reforma 222' }, { name: 'Calle 5' }];
  assert.deepEqual(merge('reforma', local, online, 5).map((s) => s.name), ['Reforma 222', 'Roma', 'Calle 5']);
  assert.deepEqual(merge('reforma 222', local, online, 5).map((s) => s.name), ['reforma 222', 'Calle 5', 'Roma']);
});
