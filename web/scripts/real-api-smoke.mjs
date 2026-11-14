// A smoke check of the web against the REAL API (Frontend plan §10.4), run by hand — not in the CI:
//   1. the API in test mode:  $env:API_FAKE_ROLES = "1"; uv run python pipelines/scripts/api/Serve.py --fake-roles
//   2. the web:               npm --prefix web run dev
//   3. this:                  node web/scripts/real-api-smoke.mjs [--shots <folder>]
// Reads the test logins from web/.env.local (git-ignored; never printed). Prints one ✅ / ❌ line per check.
import { readFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const BASE = process.env.WEB_BASE_URL ?? "http://localhost:3000";
const shots = process.argv.includes("--shots") ? process.argv[process.argv.indexOf("--shots") + 1] : null;
const env = Object.fromEntries(
  readFileSync(new URL("../.env.local", import.meta.url), "utf8")
    .split(/\r?\n/)
    .filter((l) => l && !l.startsWith("#") && l.includes("="))
    .map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]),
);

let failed = 0;
const check = (ok, line) => {
  console.log(`${ok ? "✅" : "❌"} ${line}`);
  if (!ok) failed++;
};

async function signIn(page, email, password) {
  await page.goto(`${BASE}/login?next=%2Fask`);
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/ask$/, { timeout: 20_000 });
}

async function ask(page, question) {
  await page
    .getByRole("status")
    .filter({ hasText: /API (ready|degraded|offline)/ })
    .waitFor({ timeout: 20_000 });
  await page.getByRole("textbox", { name: "Ask PortPilot" }).last().fill(question);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
}

const browser = await chromium.launch();
try {
  // a Finance manager: the scripted model calls finance_kpi on the real views → an answer with real receipts
  const fin = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  await signIn(fin, env.WEB_E2E_FINANCE_EMAIL, env.WEB_E2E_FINANCE_PASSWORD);
  check(true, `signed in as the Finance manager (${env.WEB_E2E_FINANCE_EMAIL})`);
  await ask(fin, "How much did PortPilot bill in week 23 of 2025?");
  const chips = fin.getByRole("button", { name: /^See where .* comes from$/ });
  await chips.first().waitFor({ timeout: 60_000 });
  const n = await chips.count();
  check(n === 3, `the answer carries ${n} number receipts (expected 3: billed, budget, collected)`);
  await chips.first().click();
  const slip = fin.getByRole("dialog");
  const slipText = (await slip.textContent()) ?? "";
  check(
    slipText.includes("billed_sdr") &&
      slipText.includes("finance.kpi_weekly") &&
      slipText.includes("report_week = 23"),
    "the first receipt names billed_sdr, finance.kpi_weekly, report_week = 23",
  );
  if (shots) await fin.screenshot({ path: `${shots}/real-api-finance.png` });
  await fin.keyboard.press("Escape");

  // a chart by choice (no model): the API draws the ViewSpec from the real finance views
  await fin.goto(`${BASE}/views`);
  await fin
    .getByRole("status")
    .filter({ hasText: /API (ready|degraded|offline)/ })
    .waitFor({ timeout: 20_000 });
  await fin.getByLabel("Week of 2025").selectOption("23");
  await fin.getByRole("button", { name: "Draw the chart" }).click();
  await fin.locator("td[data-value]").first().waitFor({ state: "attached", timeout: 60_000 });
  const rows = await fin.locator("td[data-value]").count();
  check(rows > 0, `a chart by choice drawn from the real views (${rows} values in its table)`);
  if (shots) await fin.screenshot({ path: `${shots}/real-api-views.png` });

  // the finance pages (D-FE-7): week 23 billed = the golden value; W15 = a pack published through the API (ADR-067)
  await fin.goto(`${BASE}/finance?week=23&page=overview`);
  await fin.getByRole("button", { name: /8.39M SDR/ }).waitFor({ timeout: 60_000 });
  check(true, "Overview, week 23: billed 8.39M SDR with its receipt (= finance_kpi, the golden value)");
  await fin.goto(`${BASE}/finance?week=15&page=executive`);
  const panel = fin.getByLabel("This week's pack");
  await panel.locator("li").first().waitFor({ timeout: 60_000 });
  check(
    (await panel.locator("li").count()) > 0,
    `Executive, W15: the published pack's summary (${await panel.locator("li").count()} lines)`,
  );
  if (shots) await fin.screenshot({ path: `${shots}/real-api-finance-w15.png`, fullPage: true });

  // an operations employee: the finance tool is refused before any model sees it
  const ops = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  await signIn(ops, env.WEB_E2E_EMPLOYEE_OPERATIONS_EMAIL, env.WEB_E2E_EMPLOYEE_OPERATIONS_PASSWORD);
  await ask(ops, "How much did PortPilot bill in week 23 of 2025?");
  await ops.getByText("not part of your access").first().waitFor({ timeout: 60_000 });
  check(
    (await ops.getByRole("button", { name: /^See where/ }).count()) === 0,
    "an operations employee: refused, no figures",
  );
  if (shots) await ops.screenshot({ path: `${shots}/real-api-operations.png` });

  // F6 — the voyage watch from the saved runs (no model): alerts, the high filter, the run's brief and fleet counts
  await ops.goto(`${BASE}/voyages`);
  const alertRows = ops.getByRole("list", { name: "Alerts by severity" }).getByRole("listitem");
  await alertRows.first().waitFor({ timeout: 60_000 });
  const shown = (await ops.getByText(/^Showing \d+ of \d+ alerts/).textContent()) ?? "";
  const [, all, of] = /Showing (\d+) of (\d+)/.exec(shown) ?? [];
  check(Number(all) > 0 && all === of, `the watch: the latest run's ${all} alerts listed (of ${of})`);
  await ops.getByLabel("Fleet at the run's clock").locator("dd").first().waitFor({ timeout: 60_000 });
  const watched =
    (await ops.getByLabel("Fleet at the run's clock").locator("dd").first().textContent()) ?? "";
  check(/^\d[\d,]*$/.test(watched.trim()), `the run's fleet counts: ${watched.trim()} vessels watched`);
  const briefChips = ops.getByRole("list", { name: "The brief" }).getByRole("button", { name: /^See where/ });
  const nb = await briefChips.count();
  if (nb) {
    await briefChips.first().click();
    const t = (await ops.getByRole("dialog").textContent()) ?? "";
    check(/watch\.(alerts|fleet)/.test(t), `the brief carries ${nb} receipts; the first names its evidence`);
    await ops.keyboard.press("Escape");
  } else check(true, "the run has no written brief (brief_status not ok): alerts only");
  const board = ops.getByRole("table", { name: "ETA by rule for the vessels at sea" });
  await board.locator("tbody tr").first().waitFor({ timeout: 60_000 });
  const more = ops.getByRole("button", { name: /^Show all \d+ vessels at sea$/ });
  const atSea = /\d+/.exec((await more.textContent()) ?? "")?.[0];
  const firstEta = await board.locator('[data-field="eta_in_h"]').first().getAttribute("data-value");
  check(
    Number(atSea) > 0 && firstEta !== null,
    `the ETA board (D-FE-10): ${atSea} vessels at sea by rule; the first row's eta_in_h = ${firstEta} (the API's)`,
  );
  const runLinks = ops.getByRole("list", { name: "Watch runs" }).getByRole("link");
  await runLinks.first().waitFor({ timeout: 90_000 });
  check((await runLinks.count()) > 0, `the watch runs list: ${await runLinks.count()} runs (newest 20)`);
  if (shots) await ops.screenshot({ path: `${shots}/real-api-voyages.png`, fullPage: true });
  await ops.getByRole("button", { name: "High only" }).click();
  await ops.waitForURL(/high=1$/);
  await ops.getByText(/^Showing \d+ of \d+ alerts/).waitFor();
  const high = /Showing (\d+) of/.exec((await ops.getByText(/^Showing \d+ of/).textContent()) ?? "")?.[1];
  check(Number(high) <= Number(all), `High only: ${high} of ${of} alerts (from the API's filter)`);

  // F6 — route advice: the page and the stored advice (a new advice needs a real model; --fake-roles is unscripted)
  await ops.goto(`${BASE}/routes`);
  const earlier = ops.getByRole("list", { name: "Earlier advice" });
  await earlier.waitFor({ timeout: 60_000 });
  await ops.waitForTimeout(1500);
  const stored = await earlier.getByRole("link").count();
  if (stored) {
    await earlier.getByRole("link").first().click();
    await ops.getByRole("region", { name: /^Via / }).first().waitFor({ timeout: 60_000 });
    check(true, `route advice: ${stored} stored advice; the first opens with its route cards`);
    if (shots) await ops.screenshot({ path: `${shots}/real-api-routes.png`, fullPage: true });
  } else check(true, "route advice: the page opens; no stored advice for this login yet");
} catch (error) {
  check(false, `stopped: ${String(error).split("\n")[0]}`);
} finally {
  await browser.close();
}
process.exit(failed ? 1 : 0);
