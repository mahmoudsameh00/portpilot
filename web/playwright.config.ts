import { defineConfig, devices } from "@playwright/test";

// One runner for logic tests, E2E and accessibility (Frontend plan §10). The tests run a production build on port
// 3100 against the mock API (tests/mock-api.mjs, port 8765): database-free, the same locally and in CI, and never in
// the way of the dev server on 3000.
const CI = !!process.env.CI;
const WEB = "http://localhost:3100";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: CI,
  retries: CI ? 1 : 0,
  reporter: CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: { baseURL: WEB, trace: "retain-on-failure" },
  projects: [
    { name: "logic", testMatch: /.*\.logic\.spec\.ts/ },
    { name: "desktop", testMatch: /.*\.e2e\.spec\.ts/, use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", testMatch: /.*\.e2e\.spec\.ts/, use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: "node tests/mock-api.mjs",
      url: "http://127.0.0.1:8765/api/v1/health/live",
      reuseExistingServer: false,
      env: { MOCK_API_PORT: "8765" },
    },
    {
      command: "npm run build && npx next start --port 3100 --hostname 127.0.0.1",
      url: "http://127.0.0.1:3100/login",
      reuseExistingServer: false,
      timeout: 300_000,
      env: {
        NEXT_TELEMETRY_DISABLED: "1",
        PORTPILOT_API_URL: "http://127.0.0.1:8765",
        PORTPILOT_WEB_ORIGIN: WEB,
      },
    },
  ],
});
