// npm test
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildIndex, merge, plain, searchPlaces } from './places.ts';

const file = {
  version: 1,
  kinds: ['Colonia', 'Metro', 'Edificio', 'Metrobús'],
  places: [
    ['Torre Reforma Latino', 2, 19.4253, -99.1625],
    ['Colonia Roma Norte', 0, 19.418, -99.16],
    ['Reforma', 1, 19.43, -99.15],
    ['Ángel del Pedregal', 2, 19.3, -99.2],
    ['Colonia Doctores', 0, 19.42, -99.145],
    ['Doctores', 3, 19.421, -99.146],
    ['Doctores', 1, 19.4225, -99.1438],
    ['Metro Allende', 2, 19.435, -99.137],
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
test('the kind typed with the name finds the place of that kind only', () => {
  for (const q of ['metro doctores', 'Metro Doctores', 'estación metro doctores']) {
    assert.deepEqual(searchPlaces(index, q, near, 5).map((s) => `${s.name} (${s.context})`), ['Doctores (Metro)'], q);
  }
  assert.deepEqual(searchPlaces(index, 'metrobús doctores', near, 5).map((s) => s.context), ['Metrobús']);
});
test('a kind word alone does not match places without it in the name', () => assert.deepEqual(names('metro'), ['Metro Allende']));
test('"ecobici" with a name finds the station', () => assert.equal(searchPlaces(index, 'ecobici reforma', near, 5)[0].stationId, '7'));
test('merge keeps two stations with the same name, but drops that name from Photon', () => {
  const local = [
    { name: 'Liverpool - Génova', stationId: '12' },
    { name: 'Liverpool - Génova', stationId: '13' },
  ];
  const online = [{ name: 'Liverpool - Génova' }, { name: 'Liverpool Insurgentes' }];
  assert.deepEqual(
    merge('liverpool', local, online, 5).map((s) => s.stationId ?? s.name),
    ['12', '13', 'Liverpool Insurgentes'],
  );
});
test('plain removes accents and punctuation', () => assert.equal(plain('Álvaro Obregón, CDMX!'), 'alvaro obregon cdmx'));
test('merge puts local first, online first for a street number, and drops repeated names', () => {
  const local = [{ name: 'Reforma 222' }, { name: 'Roma' }];
  const online = [{ name: 'reforma 222' }, { name: 'Calle 5' }];
  assert.deepEqual(merge('reforma', local, online, 5).map((s) => s.name), ['Reforma 222', 'Roma', 'Calle 5']);
  assert.deepEqual(merge('reforma 222', local, online, 5).map((s) => s.name), ['reforma 222', 'Calle 5', 'Roma']);
});
