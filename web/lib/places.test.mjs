// npm test
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { estimateInBlock, estimatePoint, buildAddresses, buildIndex, buildStreets, geocode, merge, plain, searchAddresses, searchPlaces, searchStreets } from './places.ts';

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

test('each suggestion tells its source', () => {
  assert.equal(searchPlaces(index, 'rio tiber', near, 1)[0].source, 'station');
  assert.equal(searchPlaces(index, 'torre reforma', near, 1)[0].source, 'index');
});

test('a Photon place keeps its OpenStreetMap id; a street address is an address', async () => {
  const feature = (properties) => ({ geometry: { coordinates: [-99.17, 19.42] }, properties });
  const features = [
    feature({ name: 'Torre Mitikah', osm_type: 'W', osm_id: 123 }),
    feature({ street: 'Calle Falsa', housenumber: '123', osm_type: 'N', osm_id: 9 }),
  ];
  const real = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ features }) });
  try {
    const [place, address] = await geocode('torre mitikah', near, '', 5);
    assert.equal(place.source, 'photon');
    assert.equal(place.osm, 'W123');
    assert.equal(address.source, 'address');
  } finally {
    globalThis.fetch = real;
  }
});

const streetsFile = {
  version: 1,
  boroughs: ['Cuauhtémoc', 'Azcapotzalco'],
  streets: [
    ['Calle Durango', 0, [19.4206, -99.1625, 19.4222, -99.1575]],
    ['Calle Durango', 1, [19.4767, -99.1908]],
    ['Eje 3 Norte', 0, [19.44, -99.15]],
    ['Avenida Insurgentes Sur', 0, [19.41, -99.17]],
  ],
};
const streets = buildStreets(streetsFile);
const streetNames = (q) => searchStreets(streets, q, near, 5).map((s) => `${s.name} (${s.context})`);

test('a street with a house number gives the street, nearest first', () => {
  assert.deepEqual(streetNames('durango 49'), ['Calle Durango (Cuauhtémoc)', 'Calle Durango (Azcapotzalco)']);
  assert.deepEqual(streetNames('calle durango'), ['Calle Durango (Cuauhtémoc)', 'Calle Durango (Azcapotzalco)']);
});
test('a street suggestion is the point of the street nearest to the person', () => {
  const [first] = searchStreets(streets, 'durango', { lat: 19.4222, lng: -99.1576 }, 1);
  assert.deepEqual([first.lat, first.lng], [19.4222, -99.1575]);
  assert.equal(first.source, 'address');
});
test('a number in the street name is kept; a street needs every word', () => {
  assert.deepEqual(streetNames('eje 3'), ['Eje 3 Norte (Cuauhtémoc)']);
  assert.deepEqual(streetNames('durango insurgentes'), []);
});
test('no street file: no street suggestions', () => assert.deepEqual(searchStreets(buildStreets(null), 'durango', near, 5), []));

const addresses = buildAddresses({
  version: 1,
  boroughs: ['Cuauhtémoc', 'Azcapotzalco'],
  neighbourhoods: ['Roma Norte', 'Clavería'],
  streets: [
    ['Calle Durango', 0, [['49', 19.42192, -99.15708, 0], ['49A', 19.4222, -99.1571, 0], ['50', 19.4221, -99.1579, 0]]],
    ['Calle Durango', 1, [['49', 19.4767, -99.1908, 1]]],
    ['Avenida Insurgentes Sur', 0, [['300', 19.41, -99.17, 0]]],
  ],
});
const addressNames = (q) => searchAddresses(addresses, q, near, 5).map((s) => `${s.name} (${s.context})`);

test('a street and a house number give the address, nearest first', () => {
  assert.deepEqual(addressNames('durango 49'), ['Calle Durango 49 (Roma Norte, Cuauhtémoc)', 'Calle Durango 49 (Clavería, Azcapotzalco)']);
  const [first] = searchAddresses(addresses, 'calle durango 49', near, 1);
  assert.deepEqual([first.lat, first.lng, first.source], [19.42192, -99.15708, 'address']);
});
test('the house number must be the same: "49" is not "49A" or "4"', () => {
  assert.deepEqual(addressNames('durango 49a'), ['Calle Durango 49A (Roma Norte, Cuauhtémoc)']);
  assert.deepEqual(addressNames('durango 4'), []);
  assert.deepEqual(addressNames('durango 51'), []);
});
test('a text with no house number, or no street, gives no address', () => {
  assert.deepEqual(addressNames('durango'), []);
  assert.deepEqual(addressNames('49'), []);
  assert.deepEqual(addressNames('insurgentes durango 300'), []);
});
test('the number file is optional', () => assert.deepEqual(searchAddresses(buildAddresses(null), 'durango 49', near, 5), []));
test('an address before Photon: merge drops the Photon answer with the same name', () => {
  const exact = [{ name: 'Calle Durango 49', lat: 1 }];
  const online = [{ name: 'Calle Durango 49', lat: 2 }, { name: 'Durango 490' }];
  assert.deepEqual(merge('durango 49', [], [...exact, ...online], 5).map((s) => s.lat ?? s.name), [1, 'Durango 490']);
});

const estimating = buildAddresses({
  version: 1,
  boroughs: ['Benito Juárez'],
  neighbourhoods: ['Del Valle Centro'],
  streets: [
    [
      'Calle Patricio Sanz',
      0,
      [['457', 19.3700, -99.1750, 0], ['519', 19.3710, -99.1750, 0], ['518', 19.3720, -99.1750, 0], ['600', 19.3900, -99.1750, 0]],
    ],
  ],
});

test('a house number that is not in the file is estimated between its neighbours of the same side', () => {
  const [first] = searchAddresses(estimating, 'patricio sanz 489', near, 5);
  assert.equal(first.name, 'Calle Patricio Sanz 489');
  assert.equal(first.context, 'Del Valle Centro, Benito Juárez · aprox.');
  assert.ok(Math.abs(first.lat - (19.37 + (0.001 * (489 - 457)) / (519 - 457))) < 1e-9);
  assert.equal(searchAddresses(estimating, 'patricio sanz 489', near, 5, 'approx.')[0].context.endsWith('· approx.'), true);
});
test('no estimate with a neighbour on one side only, or two neighbours too far apart', () => {
  assert.equal(estimatePoint([['10', 19.37, -99.17, 0]], 12), null);
  assert.equal(estimatePoint([['10', 19.37, -99.17, 0], ['20', 19.38, -99.17, 0]], 14), null);
  assert.deepEqual(searchAddresses(estimating, 'patricio sanz 700', near, 5), []);
});
test('the side matters: an odd number is not placed between even numbers', () => {
  assert.equal(estimatePoint([['2', 19.37, -99.17, 0], ['10', 19.3705, -99.17, 0]], 5), null);
});

const blocked = buildAddresses({
  version: 1,
  boroughs: ['Benito Juárez'],
  neighbourhoods: ['Del Valle Centro'],
  streets: [
    [
      'Calle Patricio Sanz',
      0,
      [['612', 19.39, -99.1705, 0]],
      [
        [19.39334, -99.16978, 19.39209, -99.17009, [[5, 0, 100]]],
        [19.39209, -99.17009, 19.39048, -99.17049, [[6, 20, 80]]],
      ],
    ],
  ],
});

test('a number with no neighbours at each side is placed in the block of its hundred, marked as approximate', () => {
  const [first] = searchAddresses(blocked, 'patricio sanz 550', near, 5);
  assert.equal(first.name, 'Calle Patricio Sanz 550');
  assert.equal(first.context, 'Benito Juárez · aprox.');
  const t = 50 / 99;
  assert.ok(Math.abs(first.lat - (19.39334 + (19.39209 - 19.39334) * t)) < 1e-9);
  assert.ok(Math.abs(first.lng - (-99.16978 + (-99.17009 + 99.16978) * t)) < 1e-9);
});
test('the places of the hundred in the block set the point: 600 is at 20 and 699 at 80', () => {
  const block = [[19.39209, -99.17009, 19.39048, -99.17049, [[6, 20, 80]]]];
  const start = estimateInBlock(block, 600, near);
  assert.ok(Math.abs(start.lat - (19.39209 + (19.39048 - 19.39209) * 0.2)) < 1e-9);
  const end = estimateInBlock(block, 699, near);
  assert.ok(Math.abs(end.lat - (19.39209 + (19.39048 - 19.39209) * 0.8)) < 1e-9);
});
test('no block for the hundred: no estimate', () => {
  assert.equal(estimateInBlock([[19.39, -99.17, 19.391, -99.17, [[5, 0, 100]]]], 700, near), null);
  assert.deepEqual(searchAddresses(blocked, 'patricio sanz 750', near, 5), []);
});
test('two blocks with the same hundred: the nearest to the person', () => {
  const blocks = [
    [19.5, -99.1, 19.501, -99.1, [[5, 0, 100]]],
    [19.4, -99.1, 19.401, -99.1, [[5, 0, 100]]],
  ];
  assert.ok(estimateInBlock(blocks, 550, { lat: 19.4005, lng: -99.1 }).lat < 19.41);
  assert.ok(estimateInBlock(blocks, 550, { lat: 19.5005, lng: -99.1 }).lat > 19.49);
});

test('an estimate is not added next to an exact address of another street', () => {
  const withBoth = buildAddresses({
    version: 1,
    boroughs: ['Cuauhtémoc'],
    neighbourhoods: ['Roma Norte'],
    streets: [
      ['Calle Durango', 0, [['49', 19.42192, -99.15708, 0]], []],
      ['Callejón Durango', 0, [['40', 19.4229, -99.1552, 0], ['60', 19.4231, -99.1553, 0]], []],
    ],
  });
  assert.deepEqual(searchAddresses(withBoth, 'durango 49', near, 5).map((s) => s.name), ['Calle Durango 49']);
  assert.deepEqual(searchAddresses(withBoth, 'durango 50', near, 5).map((s) => s.name), ['Callejón Durango 50']);
});
