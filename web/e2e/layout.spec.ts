// Layout tests: the planner panels stay on screen, do not overlap and do not overflow. Each project in
// playwright.config.ts runs them at one screen size. The API, the basemap, the routes and Photon are fakes.

import { type Page, expect, test } from '@playwright/test';
import { DROPOFF_NAME, START_NAME, dueTrip, planResponse, stationsResponse } from './fixtures';
import { expectAbove, expectApart, expectInViewport, expectInside, expectNoOverflowX, expectNoPageScrollX } from './layout';

// Same breakpoint as PHONE in components/planner.tsx.
const PHONE_MAX_WIDTH = 700;
// The card must keep room for its title and about one row.
const CARD_MIN_HEIGHT_PX = 120;
const EMPTY_STYLE = { version: 8, glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf', sources: {}, layers: [] };

type Setup = { lang?: 'es' | 'en'; withTripQuestion?: boolean };

async function fakeNetwork(page: Page) {
  await page.route(/\/v1\/stations(\?|$)/, (route) => route.fulfill({ json: stationsResponse() }));
  await page.route(/\/v1\/plan(\?|$)/, (route) => route.fulfill({ json: planResponse() }));
  await page.route(/\/v1\/feedback(\?|$)/, (route) => route.fulfill({ json: {} }));
  await page.route('https://tiles.openfreemap.org/**', (route) =>
    route.request().url().endsWith('/styles/positron') ? route.fulfill({ json: EMPTY_STYLE }) : route.abort(),
  );
  await page.route('https://routing.openstreetmap.de/**', (route) => route.abort());
  await page.route('https://photon.komoot.io/**', (route) => route.fulfill({ json: { features: [] } }));
}

async function openPlanner(page: Page, { lang = 'es', withTripQuestion = false }: Setup = {}) {
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

async function pick(page: Page, query: string, name: string) {
  await page.getByRole('combobox').fill(query);
  await page.locator('.suggest__item', { hasText: name }).first().click();
}

async function openPlan(page: Page, setup: Setup = {}) {
  await openPlanner(page, setup);
  await pick(page, 'Niños Héroes', START_NAME);
  await pick(page, 'Acapulco Puebla', DROPOFF_NAME);
  await expect(page.locator('.card .row.is-best')).toBeVisible();
}

const isPhone = (page: Page) => page.viewportSize()!.width <= PHONE_MAX_WIDTH;

// The card height follows the dock height, which a ResizeObserver reports after the first paint.
async function expectCardFitsAboveDock(page: Page) {
  const card = page.locator('.card');
  await expect(async () => {
    await expectAbove(page.locator('.topbar'), card);
    await expectAbove(card, page.locator('.dock'));
  }).toPass();
  expect((await card.boundingBox())!.height).toBeGreaterThanOrEqual(CARD_MIN_HEIGHT_PX);
  await expectInViewport(card);
  await expectInViewport(page.locator('.dock'));
  await expectNoOverflowX(card);
  await expectNoOverflowX(page.locator('.dock'));
  await expectNoPageScrollX(page);
}

test('the start screen fits', async ({ page }) => {
  await openPlanner(page);
  const title = page.locator('.stage__title');
  await expect(title).toBeVisible();
  await expectAbove(title, page.locator('.ask'));
  await expectInViewport(title);
  await expectInViewport(page.locator('.ask'));
  await expectNoOverflowX(page.locator('.dock'));
  await expectApart(page.locator('.topbar__brand'), page.locator('.topbar__end'));
  await expectNoPageScrollX(page);
});

for (const lang of ['es', 'en'] as const) {
  test(`the plan card fits above the dock and shows the best row (${lang})`, async ({ page }) => {
    await openPlan(page, { lang });
    await expectCardFitsAboveDock(page);
    await expectInside(page.locator('.card .row.is-best'), page.locator('.card'));
    if (isPhone(page)) await expect(page.locator('.dock__context')).toBeHidden();
    else await expect(page.locator('.dock__context')).toBeVisible();
  });
}

test('the full list and the rating are reachable inside the card', async ({ page }) => {
  await openPlan(page);
  await page.locator('.card__more').click();
  await expect(page.locator('.card .row')).toHaveCount(planResponse().candidates.length);
  await expectCardFitsAboveDock(page);
  const rating = page.locator('.card .rate');
  await rating.scrollIntoViewIfNeeded();
  await expectInside(rating, page.locator('.card'));
  await expectInside(page.locator('.card__legend'), page.locator('.card'));
});

test('the card still fits when the dock asks about a past trip', async ({ page }) => {
  await openPlan(page, { withTripQuestion: true });
  await expect(page.locator('.trip-check')).toBeVisible();
  await expectCardFitsAboveDock(page);
});

test('a closed card leaves the plan summary in the dock', async ({ page }) => {
  await openPlan(page);
  await page.locator('.card__head .icon-btn').click();
  await expect(page.locator('.card')).toBeHidden();
  const summary = page.locator('.dock__context');
  await expect(summary).toBeVisible();
  await expectInViewport(page.locator('.dock'));
  await expectNoOverflowX(page.locator('.dock'));
  await expectNoPageScrollX(page);
});

test('the suggestions stay under the top bar', async ({ page }) => {
  await openPlanner(page);
  await pick(page, 'Niños Héroes', START_NAME);
  await page.getByRole('combobox').fill('Liverpool');
  const suggestions = page.locator('.suggest');
  await expect(suggestions).toBeVisible();
  await expectAbove(page.locator('.topbar'), suggestions);
  await expectInViewport(suggestions);
  await expectNoOverflowX(suggestions);
});
