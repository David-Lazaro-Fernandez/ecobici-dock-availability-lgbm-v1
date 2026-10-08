// Geometry checks for the layout tests. Each check fails with the boxes that break it, so the report tells what moved.

import { type Locator, type Page, expect } from '@playwright/test';

type Box = { x: number; y: number; width: number; height: number };
// Sub-pixel rounding of borders and transforms.
const TOLERANCE_PX = 1;

async function box(locator: Locator): Promise<Box> {
  const b = await locator.boundingBox();
  expect(b, `${locator} has no box`).not.toBeNull();
  return b!;
}

export async function expectNoPageScrollX(page: Page) {
  const { scrollWidth, clientWidth } = await page.evaluate(() => {
    const { scrollWidth, clientWidth } = document.documentElement;
    return { scrollWidth, clientWidth };
  });
  expect(scrollWidth, 'the page scrolls sideways').toBeLessThanOrEqual(clientWidth);
}

export async function expectAbove(upper: Locator, lower: Locator) {
  const [a, b] = [await box(upper), await box(lower)];
  expect(a.y + a.height, `${upper} overlaps ${lower}`).toBeLessThanOrEqual(b.y + TOLERANCE_PX);
}

export async function expectApart(first: Locator, second: Locator) {
  const [a, b] = [await box(first), await box(second)];
  const apart = a.x + a.width <= b.x + TOLERANCE_PX || b.x + b.width <= a.x + TOLERANCE_PX || a.y + a.height <= b.y + TOLERANCE_PX || b.y + b.height <= a.y + TOLERANCE_PX;
  expect(apart, `${first} overlaps ${second}: ${JSON.stringify({ a, b })}`).toBe(true);
}

export async function expectInside(inner: Locator, outer: Locator) {
  const [i, o] = [await box(inner), await box(outer)];
  const inside =
    i.x >= o.x - TOLERANCE_PX &&
    i.y >= o.y - TOLERANCE_PX &&
    i.x + i.width <= o.x + o.width + TOLERANCE_PX &&
    i.y + i.height <= o.y + o.height + TOLERANCE_PX;
  expect(inside, `${inner} is not inside ${outer}: ${JSON.stringify({ inner: i, outer: o })}`).toBe(true);
}

export async function expectInViewport(locator: Locator) {
  const b = await box(locator);
  const { width, height } = locator.page().viewportSize()!;
  expect(b.x, `${locator} starts left of the screen`).toBeGreaterThanOrEqual(-TOLERANCE_PX);
  expect(b.y, `${locator} starts above the screen`).toBeGreaterThanOrEqual(-TOLERANCE_PX);
  expect(b.x + b.width, `${locator} ends right of the screen`).toBeLessThanOrEqual(width + TOLERANCE_PX);
  expect(b.y + b.height, `${locator} ends below the screen`).toBeLessThanOrEqual(height + TOLERANCE_PX);
}

/** No visible element inside `container` goes past its left or right edge. Vertical scroll is allowed. */
export async function expectNoOverflowX(container: Locator) {
  const offenders = await container.evaluate((root, tolerance) => {
    const edge = root.getBoundingClientRect();
    const name = (el: Element) => `${el.tagName.toLowerCase()}.${[...el.classList].join('.')} "${el.textContent?.trim().slice(0, 40)}"`;
    return [...root.querySelectorAll('*')]
      .filter((el) => {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0 || getComputedStyle(el).visibility === 'hidden') return false;
        return r.left < edge.left - tolerance || r.right > edge.right + tolerance;
      })
      .map(name);
  }, TOLERANCE_PX);
  expect(offenders, `elements wider than ${container}`).toEqual([]);
}
