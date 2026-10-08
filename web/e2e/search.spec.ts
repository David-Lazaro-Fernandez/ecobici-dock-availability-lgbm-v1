// Search tests: the typed text shows the expected suggestions, the keyboard picks one, and a full trip shows the
// stations. The places come from the real public/lugares.json. The stations, the plan and Photon are fakes.

import { expect, test } from '@playwright/test';
import { DROPOFF_NAME, START_NAME, codeOf } from './fixtures';
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

test('the card shows the code only for the stations with the same name', async ({ page }) => {
  await pick(page, 'from', 'Niños Héroes', START_NAME);
  await pick(page, 'to', 'Acapulco Puebla', DROPOFF_NAME);
  await openStations(page);
  await page.locator('.card__more').click();
  const liverpool = page.locator('.card .row', { hasText: 'Liverpool - Génova' });
  await expect(liverpool.locator('.code')).toHaveText(LIVERPOOL_STATIONS.map(codeOf));
  await expect(page.locator('.card .row.is-best .code')).toHaveCount(0);
});
