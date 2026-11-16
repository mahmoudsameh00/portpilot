import { defineConfig, devices } from "@playwright/test";

// Local-stack E2E (Frontend plan §10.4, the done-when's "local-stack E2E, leakage 0"): the real API in its test mode
// (`Serve.py --fake-roles`: a scripted model, no LLM quota) over the isolated full-data PostgreSQL clone
// (`portpilot-api-full`, 127.0.0.1:55432) — never the application database — and a production build of the web.
// The owner's machine only, never CI: run it through `ops/tests/run_web_stack.ps1`, which sets the clone's variables.
// Ports 8011 / 3101 keep it apart from the real API (8000), the web container (3000) and the mocked suite (3100).
const WEB = "http://localhost:3101";
const API = "http://127.0.0.1:8011";

if (process.env.PORTPILOT_FULL_STACK_ISOLATED !== "1" || process.env.PGPORT !== "55432") {
  throw new Error("The stack E2E runs only on the isolated clone: use ops/tests/run_web_stack.ps1");
}

export default defineConfig({
  testDir: "./tests/stack",
  testMatch: /.*\.stack\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  timeout: 90_000,
  globalSetup: "./tests/stack/global-setup.ts",
  globalTeardown: "./tests/stack/global-teardown.ts",
  use: { ...devices["Desktop Chrome"], baseURL: WEB, trace: "retain-on-failure" },
  webServer: [
    {
      command: "uv run python ../pipelines/scripts/api/Serve.py --fake-roles --port 8011",
      url: `${API}/api/v1/health/live`,
      reuseExistingServer: false,
      timeout: 180_000,
      // no Sentry event and no LangSmith trace from a test run (an empty variable wins over .env)
      env: {
        API_FAKE_ROLES: "1",
        SENTRY_DSN: "",
        LANGSMITH_API_KEY: "",
        LANGCHAIN_API_KEY: "",
        PYTHONIOENCODING: "utf-8",
      },
    },
    {
      command: "npm run build && npx next start --port 3101 --hostname 127.0.0.1",
      url: "http://127.0.0.1:3101/login",
      reuseExistingServer: false,
      timeout: 300_000,
      env: { NEXT_TELEMETRY_DISABLED: "1", PORTPILOT_API_URL: API, PORTPILOT_WEB_ORIGIN: WEB },
    },
  ],
});
