// Takes the README screenshots from the real app: the static export in `out/`, the live API and the real basemap.
// The API allows only the production origin, so the script sends its requests from Node and adds the CORS header.
// Run from web/: NEXT_PUBLIC_API_URL=<api> npm run build, serve `out/` on SHOTS_URL, then node scripts/screenshots.mjs <dir>.

import { chromium, devices } from '@playwright/test';

const URL = process.env.SHOTS_URL ?? 'http://localhost:3200';
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'https://ecobici-docks.duckdns.org';
const outDir = process.argv[2] ?? '../docs/img';
const FROM = { query: 'Parque México', name: 'Parque México' };
const ADDRESS = 'Durango 49';
const TO = { query: 'Zócalo', name: 'Zócalo' };

const views = {
  movil: { ...devices['iPhone 14'] },
  escritorio: { viewport: { width: 1280, height: 800 } },
};
const isPhone = (page) => page.viewportSize().width <= 700;
const endInput = (page, end) =>
  isPhone(page) ? page.locator('.trip-form__input').nth(end === 'from' ? 0 : 1) : page.locator('.ask__input');

async function viaNode(route) {
  const request = route.request();
  const response = await fetch(request.url(), { method: request.method(), body: request.postData() ?? undefined });
  await route.fulfill({
    status: response.status,
    contentType: 'application/json',
    headers: { 'access-control-allow-origin': '*' },
    body: await response.text(),
  });
}

async function pick(page, end, place) {
  await endInput(page, end).fill(place.query);
  const item = page.locator('.suggest__item').filter({ hasText: place.name }).first();
  await item.waitFor({ timeout: 15_000 });
  await item.click();
}

const browser = await chromium.launch();
for (const [name, options] of Object.entries(views)) {
  const context = await browser.newContext({ ...options, timezoneId: 'America/Mexico_City', locale: 'es-MX' });
  await context.addInitScript(() => {
    localStorage.setItem('ecobici-help-hidden-v1', '1');
    localStorage.setItem('ecobici-lang-v1', 'es');
  });
  const page = await context.newPage();
  await page.route(`${API_URL}/**`, viaNode);
  await page.goto(URL);

  await endInput(page, 'from').fill(ADDRESS);
  await page.locator('.suggest__item').first().waitFor({ timeout: 15_000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${outDir}/${name}-busqueda.png` });

  await pick(page, 'from', FROM);
  await pick(page, 'to', TO);
  await page.locator('.card .row.is-best').waitFor({ timeout: 30_000 });
  await page.waitForTimeout(4000);
  await page.screenshot({ path: `${outDir}/${name}-plan.png` });
  await context.close();
}
await browser.close();
