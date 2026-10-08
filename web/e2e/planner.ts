// Steps shared by the end-to-end specs: fake network, open the planner, pick the ends of a trip.

import { type Page, expect } from '@playwright/test';
import { DROPOFF_NAME, START_NAME, dueTrip, planResponse, stationsResponse } from './fixtures';

// Same breakpoint as PHONE in lib/phone.ts.
const PHONE_MAX_WIDTH = 700;
const EMPTY_STYLE = { version: 8, glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf', sources: {}, layers: [] };

export type End = 'from' | 'to';
export type Setup = { lang?: 'es' | 'en'; withTripQuestion?: boolean };

/** The API, the basemap, the routes and Photon are fakes. Photon finds nothing, so the local index answers. */
export async function fakeNetwork(page: Page) {
  await page.route(/\/v1\/stations(\?|$)/, (route) => route.fulfill({ json: stationsResponse() }));
  await page.route(/\/v1\/plan(\?|$)/, (route) => route.fulfill({ json: planResponse() }));
  await page.route(/\/v1\/feedback(\?|$)/, (route) => route.fulfill({ json: {} }));
  await page.route('https://tiles.openfreemap.org/**', (route) =>
    route.request().url().endsWith('/styles/positron') ? route.fulfill({ json: EMPTY_STYLE }) : route.abort(),
  );
  await page.route('https://routing.openstreetmap.de/**', (route) => route.abort());
  await page.route('https://photon.komoot.io/**', (route) => route.fulfill({ json: { features: [] } }));
}

export async function openPlanner(page: Page, { lang = 'es', withTripQuestion = false }: Setup = {}) {
  await fakeNetwork(page);
  const trip = withTripQuestion ? JSON.stringify(dueTrip()) : null;
  await page.addInitScript(
    ({ lang, trip }) => {
      localStorage.setItem('ecobici-help-hidden-v1', '1');
      localStorage.setItem('ecobici-lang-v1', lang);
      if (trip) localStorage.setItem('ecobici-trip-v1', trip);
    },
    { lang, trip },
  );
  await page.goto('/');
}

export const isPhone = (page: Page) => page.viewportSize()!.width <= PHONE_MAX_WIDTH;

// A phone has one input for each end of the trip. The desktop bar has one input for the end being edited.
export const searchBox = (page: Page) => page.locator(isPhone(page) ? '.trip-form' : '.ask');
export const endInput = (page: Page, end: End) =>
  isPhone(page) ? page.locator('.trip-form__input').nth(end === 'from' ? 0 : 1) : page.locator('.ask__input');
export const suggestions = (page: Page) => page.locator('.suggest__item');

/** The picked place as the page shows it: the phone input value, or the desktop trip end button. */
export async function expectPicked(page: Page, end: End, name: string) {
  if (isPhone(page)) await expect(endInput(page, end)).toHaveValue(name);
  else await expect(page.locator('.dock__ends .end').nth(end === 'from' ? 0 : 1)).toContainText(name);
}

export async function pick(page: Page, end: End, query: string, name: string) {
  await endInput(page, end).fill(query);
  await suggestions(page).filter({ hasText: name }).first().click();
}

/** On a phone, open the stations drawer, so that all the card content is on screen. A desktop has no drawer. */
export async function openStations(page: Page) {
  if (!isPhone(page)) return;
  const handle = page.locator('.drawer__handle');
  if ((await handle.getAttribute('aria-expanded')) !== 'true') await handle.click();
  await expect(page.locator('.drawer')).toHaveClass(/is-open/);
}

export async function openPlan(page: Page, setup: Setup = {}) {
  await openPlanner(page, setup);
  await pick(page, 'from', 'Niños Héroes', START_NAME);
  await pick(page, 'to', 'Acapulco Puebla', DROPOFF_NAME);
  await expect(page.locator('.card .row.is-best')).toBeVisible();
}
