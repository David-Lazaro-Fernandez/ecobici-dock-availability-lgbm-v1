// Layout tests in e2e/. They run on the static export, as in production, at the phone sizes in `projects`.
// Run: npx playwright install chromium (once), then npm run test:e2e.

import { defineConfig, devices } from '@playwright/test';

const PORT = 3100;
const BASE_URL = `http://localhost:${PORT}`;
const CI = Boolean(process.env.CI);

// Chromium only, so one browser download covers every phone size.
const phone = (device: keyof typeof devices) => ({ name: device, use: { ...devices[device], browserName: 'chromium' as const } });

export default defineConfig({
  testDir: 'e2e',
  fullyParallel: true,
  forbidOnly: CI,
  retries: CI ? 1 : 0,
  reporter: CI ? 'github' : 'list',
  use: {
    baseURL: BASE_URL,
    timezoneId: 'America/Mexico_City',
    // Without the slide of the dock, the boxes are final at once.
    contextOptions: { reducedMotion: 'reduce' },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [phone('Galaxy S8'), phone('iPhone SE'), phone('iPhone 14'), phone('Pixel 7'), { name: 'Desktop', use: devices['Desktop Chrome'] }],
  webServer: {
    command: `npm run build && python3 -m http.server ${PORT} --directory out`,
    url: BASE_URL,
    reuseExistingServer: !CI,
    timeout: 180_000,
  },
});
