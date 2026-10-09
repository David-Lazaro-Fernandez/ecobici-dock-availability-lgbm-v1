// Search tests: the typed text shows the expected suggestions, the keyboard picks one, and a full trip shows the
// stations. The places come from the real public/lugares.json. The stations, the plan and Photon are fakes.

import { type Page, expect, test } from '@playwright/test';
import { DROPOFF_NAME, START_NAME, codeOf, planResponse } from './fixtures';
import { endInput, expectPicked, openPlanner, openStations, pick, suggestions } from './planner';

const NO_RESULTS = 'No hay resultados en la zona de Ecobici. Agrega la colonia.';
// Index of the "Liverpool - Génova" stations in fixtures.ts.
const LIVERPOOL_STATIONS = [12, 13];

test.beforeEach(async ({ page }) => openPlanner(page));

for (const [query, name] of [
  ['metro doctores', 'Doctores'],
  ['metro niños héroes', 'Niños Héroes'],
  ['metro revolución', 'Revolución'],
  ['Metro Salto del Agua', 'Salto del Agua'],
]) {
  test(`"${query}" suggests the Metro station first`, async ({ page }) => {
    await endInput(page, 'from').fill(query);
    // The suggestion text is the name, then the kind.
    await expect(suggestions(page).first()).toHaveText(new RegExp(`^${name}.* Metro$`));
  });
}

test('"metro doctores" does not suggest the neighbourhood or the Metrobús stop', async ({ page }) => {
  await endInput(page, 'from').fill('metro doctores');
  await expect(suggestions(page)).toHaveText(['Doctores Metro']);
});

test('two Ecobici stations with the same name both come first, each with its code', async ({ page }) => {
  await endInput(page, 'from').fill('Liverpool');
  const texts = await suggestions(page).allTextContents();
  const stations = LIVERPOOL_STATIONS.map((i) => `Liverpool - Génova Estación Ecobici ${codeOf(i)}`);
  expect(texts.slice(0, 2).map((t) => t.replace(/\s+/g, ' ').trim()).sort()).toEqual(stations.sort());
});

test('Enter picks the first suggestion', async ({ page }) => {
  await endInput(page, 'from').fill('metro doctores');
  await expect(suggestions(page).first()).toBeVisible();
  await endInput(page, 'from').press('Enter');
  await expectPicked(page, 'from', 'Doctores');
});

test('the arrow keys move the choice before Enter', async ({ page }) => {
  await endInput(page, 'from').fill('metro revolución');
  const second = suggestions(page).nth(1);
  const secondName = (await second.locator('strong').textContent())!;
  await endInput(page, 'from').press('ArrowDown');
  await expect(second).toHaveClass(/is-active/);
  await endInput(page, 'from').press('Enter');
  await expectPicked(page, 'from', secondName);
});

test('a text without places tells the person to add the neighbourhood', async ({ page }) => {
  await endInput(page, 'from').fill('zzqx wvvk');
  await expect(suggestions(page)).toHaveCount(0);
  await endInput(page, 'from').press('Enter');
  await expect(page.getByText(NO_RESULTS)).toBeVisible();
});

test('a full trip shows the drop-off stations with their chance', async ({ page }) => {
  await pick(page, 'from', 'Niños Héroes', START_NAME);
  await expectPicked(page, 'from', START_NAME);
  await pick(page, 'to', 'Acapulco Puebla', DROPOFF_NAME);
  await expectPicked(page, 'to', DROPOFF_NAME);
  const best = page.locator('.card .row.is-best');
  await expect(best).toContainText(DROPOFF_NAME);
  await expect(best.locator('.card__chance')).toHaveText(/\d+ %/);
  await expect(page.locator('.card__pickup')).toContainText('Claudio Bernard-Dr. Liceaga');
});

test('the availability sort selects its first row, and a picked row stays selected', async ({ page }) => {
  const plan = planResponse();
  plan.candidates[2].p_free = 0.999;
  await page.route(/\/v1\/plan(\?|$)/, (route) => route.fulfill({ json: plan }));
  await pick(page, 'from', 'Niños Héroes', START_NAME);
  await pick(page, 'to', 'Acapulco Puebla', DROPOFF_NAME);
  await openStations(page);
  const rows = page.locator('.card .row');
  const selected = page.locator('.card .row.is-selected .row__rank');
  await expect(selected).toHaveText('1');
  await page.getByRole('radio', { name: 'Ordenar por probabilidad de lugar libre' }).click();
  await expect(rows.first().locator('.row__rank')).toHaveText('3');
  await expect(selected).toHaveText('3');
  await rows.nth(1).click();
  await expect(selected).toHaveText('1');
  await page.getByRole('radio', { name: 'Ordenar por tiempo de viaje' }).click();
  await expect(selected).toHaveText('1');
});

test('the card shows the code only for the stations with the same name', async ({ page }) => {
  await pick(page, 'from', 'Niños Héroes', START_NAME);
  await pick(page, 'to', 'Acapulco Puebla', DROPOFF_NAME);
  await openStations(page);
  await page.locator('.card__more').click();
  const liverpool = page.locator('.card .row', { hasText: 'Liverpool - Génova' });
  await expect(liverpool.locator('.code')).toHaveText(LIVERPOOL_STATIONS.map(codeOf));
  await expect(page.locator('.card .row.is-best .code')).toHaveCount(0);
});

// Two Photon answers at the same point: a named place and a street address.
const PHOTON_FEATURES = [
  { name: 'Plaza Ficticia', osm_type: 'W', osm_id: 42 },
  { street: 'Calle Ficticia', housenumber: '12', osm_type: 'N', osm_id: 7 },
].map((properties) => ({ geometry: { coordinates: [-99.16, 19.42] }, properties }));

/** The query of each plan request, in order. */
async function planQueries(page: Page) {
  await page.route('https://photon.komoot.io/**', (route) => route.fulfill({ json: { features: PHOTON_FEATURES } }));
  const plans: URLSearchParams[] = [];
  page.on('request', (r) => {
    if (/\/v1\/plan\?/.test(r.url())) plans.push(new URL(r.url()).searchParams);
  });
  return plans;
}

test('the plan request names the start station and the Photon place, with a plan id', async ({ page }) => {
  const plans = await planQueries(page);
  await pick(page, 'from', 'Niños Héroes', START_NAME);
  await pick(page, 'to', 'plaza ficticia', 'Plaza Ficticia');
  await expect.poll(() => plans.length).toBeGreaterThan(0);
  expect(Object.fromEntries(plans.at(-1)!)).toMatchObject({
    from_kind: 'station',
    from_name: START_NAME,
    to_kind: 'photon',
    to_name: 'Plaza Ficticia',
    to_osm: 'W42',
  });
  expect(plans.at(-1)!.get('plan_id')).toMatch(/^[0-9a-f-]{36}$/);
});

test('the plan request sends no name for a street address', async ({ page }) => {
  const plans = await planQueries(page);
  await pick(page, 'from', 'Niños Héroes', START_NAME);
  await pick(page, 'to', 'calle ficticia', 'Calle Ficticia 12');
  await expect.poll(() => plans.at(-1)?.get('to_kind')).toBe('address');
  expect(plans.at(-1)!.has('to_name')).toBe(false);
  expect(plans.at(-1)!.has('to_osm')).toBe(false);
});
