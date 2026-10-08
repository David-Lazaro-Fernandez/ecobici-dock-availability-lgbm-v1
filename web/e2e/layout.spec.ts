// Layout tests: the planner panels stay on screen, do not overlap and do not overflow. Each project in
// playwright.config.ts runs them at one screen size. A desktop shows the card above the dock. A phone shows the trip
// bar at the top and the stations drawer at the foot.

import { type Page, expect, test } from '@playwright/test';
import { DROPOFF_NAME, START_NAME, planResponse } from './fixtures';
import { expectAbove, expectApart, expectInViewport, expectInside, expectNoOverflowX, expectNoPageScrollX } from './layout';
import { endInput, expectPicked, isPhone, openPlan, openPlanner, openStations, pick, searchBox } from './planner';

// The card must keep room for its title and about one row.
const CARD_MIN_HEIGHT_PX = 120;
// The closed drawer must leave most of the map in view.
const DRAWER_PEEK_MAX_SHARE = 0.6;

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

async function expectTripBarFits(page: Page) {
  const bar = page.locator('.trip-bar');
  await expect(bar).toBeVisible();
  await expectInViewport(bar);
  await expect(async () => expectApart(bar, page.locator('.topbar__end'))).toPass();
  await expectAbove(bar, page.locator('.drawer'));
}

// The closed drawer shows the first station row, and the map above it.
async function expectClosedDrawerFits(page: Page) {
  const drawer = page.locator('.drawer');
  await expect(drawer).not.toHaveClass(/is-open/);
  await expectTripBarFits(page);
  await expect(async () => expectInViewport(page.locator('.card__list > li').first())).toPass();
  const { height } = page.viewportSize()!;
  const shown = height - (await drawer.boundingBox())!.y;
  expect(shown, 'the closed drawer covers most of the map').toBeLessThanOrEqual(height * DRAWER_PEEK_MAX_SHARE);
  await expectNoOverflowX(drawer);
  await expectNoPageScrollX(page);
}

test('the start screen fits', async ({ page }) => {
  await openPlanner(page);
  const title = page.locator('.stage__title');
  await expect(title).toBeVisible();
  await expectAbove(title, searchBox(page));
  await expectInViewport(title);
  await expectInViewport(searchBox(page));
  await expectNoOverflowX(page.locator('.dock'));
  await expectApart(page.locator('.topbar__end'), title);
  await expectInViewport(page.locator('.topbar__end'));
  if (isPhone(page)) await expect(page.locator('.topbar__brand')).toBeHidden();
  else await expectApart(page.locator('.topbar__brand'), page.locator('.topbar__end'));
  await expectNoPageScrollX(page);
});

test('on a phone, the language switch floats at the top right over the map', async ({ page }) => {
  test.skip(!isPhone(page), 'phone layout only');
  await openPlanner(page);
  const corner = page.locator('.topbar__end');
  const { width } = page.viewportSize()!;
  const box = (await corner.boundingBox())!;
  expect(box.y).toBeLessThan(box.height);
  expect(width - (box.x + box.width)).toBeLessThan(box.height);
  await expect(page.locator('.lang .flag')).toHaveCount(2);
  await expect(page.locator('.lang .flag').first()).toBeVisible();
  await expect(page.locator('.lang__code').first()).toBeHidden();
  await expect(page.locator('.topbar__help'), 'the start screen has no help button').toBeHidden();
  const map = (await page.locator('.stage__map').boundingBox())!;
  expect(map.y, 'the map starts at the top of the screen').toBe(0);
});

test('on a phone, the map shows only when the trip has both ends', async ({ page }) => {
  test.skip(!isPhone(page), 'phone layout only');
  await openPlanner(page);
  const stage = page.locator('.stage');
  const glass = page.locator('.stage__glass');
  await expectAbove(page.locator('.trip-form__row').first(), page.locator('.trip-form__row').last());
  await pick(page, 'from', 'Niños Héroes', START_NAME);
  await expect(stage).not.toHaveClass(/is-located/);
  await expect(glass).toHaveCSS('opacity', '1');
  await expect(endInput(page, 'from')).toHaveValue(START_NAME);
  await expect(endInput(page, 'to')).toBeFocused();
  await pick(page, 'to', 'Acapulco Puebla', DROPOFF_NAME);
  await expect(stage).toHaveClass(/is-located/);
  await expect(glass).toHaveCSS('opacity', '0');
  await expect(page.locator('.trip-bar')).toHaveText(DROPOFF_NAME);
  await expect(searchBox(page)).toBeHidden();
});

test('on a phone, the trip bar opens the trip form, and the back button closes it', async ({ page }) => {
  test.skip(!isPhone(page), 'phone layout only');
  await openPlan(page);
  const stage = page.locator('.stage');
  await page.locator('.trip-bar').click();
  await expect(stage).not.toHaveClass(/is-located/);
  await expect(page.locator('.drawer')).toHaveCount(0);
  await expectPicked(page, 'from', START_NAME);
  await expectPicked(page, 'to', DROPOFF_NAME);
  await page.locator('.stage__back').click();
  await expect(stage).toHaveClass(/is-located/);
  await expectClosedDrawerFits(page);

  await page.locator('.trip-bar').click();
  await pick(page, 'to', 'Liverpool', 'Liverpool - Génova');
  await expect(stage).toHaveClass(/is-located/);
  await expect(page.locator('.trip-bar')).toHaveText('Liverpool - Génova');
});

test('on a phone, the new search button clears both ends and opens the start screen', async ({ page }) => {
  test.skip(!isPhone(page), 'phone layout only');
  await openPlan(page);
  const reset = page.locator('.trip-reset');
  await expectApart(reset, page.locator('.trip-bar'));
  const help = page.locator('.topbar__help');
  await expect(help).toBeVisible();
  const helpBox = (await help.boundingBox())!;
  expect(helpBox.x, 'the help is at the left edge').toBeLessThan(helpBox.width);
  expect(helpBox.width).toBe(24);
  await expectApart(reset, help);
  await expectAbove(page.locator('.maplibregl-ctrl-attrib'), help);
  await reset.click();
  await expect(page.locator('.stage')).not.toHaveClass(/is-located/);
  await expect(page.locator('.stage__title')).toBeVisible();
  await expect(help).toBeHidden();
  await expect(page.locator('.trip-bar')).toHaveCount(0);
  await expect(page.locator('.drawer')).toHaveCount(0);
  await expect(endInput(page, 'from')).toHaveValue('');
  await expect(endInput(page, 'to')).toHaveValue('');
});

test('on a phone, the handle opens and closes the drawer', async ({ page }) => {
  test.skip(!isPhone(page), 'phone layout only');
  await openPlan(page);
  const drawer = page.locator('.drawer');
  await openStations(page);
  await expectAbove(page.locator('.trip-bar'), drawer);
  await expect(page.locator('.sort')).toBeVisible();
  const legend = page.locator('.card__legend');
  await legend.scrollIntoViewIfNeeded();
  await expectInside(legend, drawer);
  await expectInViewport(legend);
  await page.locator('.drawer__handle').click();
  await expect(drawer).not.toHaveClass(/is-open/);
  await expectClosedDrawerFits(page);
});

for (const lang of ['es', 'en'] as const) {
  test(`the plan fits on screen and shows the best row (${lang})`, async ({ page }) => {
    await openPlan(page, { lang });
    if (isPhone(page)) {
      await expectClosedDrawerFits(page);
      await expect(page.locator('.dock__context')).toBeHidden();
      return;
    }
    await expectCardFitsAboveDock(page);
    await expectInside(page.locator('.card .row.is-best'), page.locator('.card'));
    await expect(page.locator('.dock__context')).toBeVisible();
  });
}

test('the full list and the rating are reachable inside the card', async ({ page }) => {
  await openPlan(page);
  await openStations(page);
  await page.locator('.card__more').click();
  await expect(page.locator('.card .row')).toHaveCount(planResponse().candidates.length);
  if (isPhone(page)) await expectAbove(page.locator('.trip-bar'), page.locator('.drawer'));
  else await expectCardFitsAboveDock(page);
  const rating = page.locator('.card .rate');
  await rating.scrollIntoViewIfNeeded();
  await expectInside(rating, page.locator('.card'));
  await expectInViewport(rating);
});

test('the question about a past trip fits', async ({ page }) => {
  await openPlan(page, { withTripQuestion: true });
  const question = page.locator('.trip-check');
  if (isPhone(page)) {
    await expectClosedDrawerFits(page);
    await openStations(page);
    await question.scrollIntoViewIfNeeded();
    await expectInside(question, page.locator('.drawer'));
    await expectInViewport(question);
    return;
  }
  await expect(question).toBeVisible();
  await expectCardFitsAboveDock(page);
});

test('a closed card leaves the plan summary in the dock', async ({ page }) => {
  test.skip(isPhone(page), 'a phone has the drawer, which does not close');
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
  await pick(page, 'from', 'Niños Héroes', START_NAME);
  await endInput(page, 'to').fill('Liverpool');
  const suggestions = page.locator('.suggest');
  await expect(suggestions).toBeVisible();
  await expectAbove(page.locator('.topbar'), suggestions);
  await expectInViewport(suggestions);
  await expectNoOverflowX(suggestions);
});
