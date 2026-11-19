// F6: the voyage watch (plan §6.7) against the mock API — the radar list (high / all in the URL), the run's brief
// with receipts and fleet counts, the runs list, a run without a brief; refusals.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import fixtures from "./fixtures/users.json" with { type: "json" };

const user = (email: string) => fixtures.users.find((u) => u.email === email)!;
const ops = user("ops.employee@portpilot.test");
const finance = user("finance.manager@portpilot.test");

test.describe.configure({ mode: "serial" });
test.skip(({ isMobile }) => isMobile, "the watch flow runs once, on desktop");

async function signedIn(page: Page, u: { email: string; password: string }, next = "/voyages") {
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Work email").fill(u.email);
  await page.getByLabel("Password").fill(u.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(
    (url) => decodeURIComponent(url.pathname) === decodeURIComponent(next.split("?")[0]!),
  );
  await expect(page.getByRole("status").filter({ hasText: /API (ready|degraded|offline)/ })).toBeVisible();
}

test("the latest run's alerts as a radar list, filtered in the URL, with the brief's receipts", async ({
  page,
}) => {
  await signedIn(page, ops);
  await expect(page.getByRole("heading", { name: "Voyage watch" })).toBeVisible();
  const alerts = page.getByRole("list", { name: "Alerts by severity" });
  await expect(alerts.getByRole("listitem")).toHaveCount(5);
  await expect(page.getByText(/Showing 5 of 5 alerts/)).toBeVisible();
  await expect(page.getByRole("img", { name: "Voyage alerts by severity" })).toBeVisible();
  await expect(alerts.getByRole("listitem").first()).toContainText("Cruise Voyager 234");
  await expect(alerts.getByRole("listitem").first()).toContainText("High");

  await page.getByRole("button", { name: "High only" }).click();
  await expect(page).toHaveURL(/\/voyages\?high=1$/);
  await expect(alerts.getByRole("listitem")).toHaveCount(3);
  await expect(page.getByText(/Showing 3 of 5 alerts/)).toBeVisible();
  await expect(page.getByRole("button", { name: "High only" })).toHaveAttribute("aria-pressed", "true");
  await page.reload();
  await expect(alerts.getByRole("listitem")).toHaveCount(3);
  await page.getByRole("button", { name: "All", exact: true }).click();
  await expect(page).toHaveURL(/\/voyages$/);
  await expect(alerts.getByRole("listitem")).toHaveCount(5);

  // the brief: headline + items with receipts; fleet counts
  const brief = page.getByRole("list", { name: "The brief" });
  await expect(brief.getByRole("listitem")).toHaveCount(2);
  await brief.getByRole("button", { name: /40\.2/ }).click();
  const slip = page.getByRole("dialog");
  await expect(slip).toContainText("wind_speed_10m_max_kn");
  await expect(slip).toContainText("watch.alerts");
  await expect(slip).toContainText("alert = 234/weather");
  await page.keyboard.press("Escape");
  const fleet = page.getByLabel("Fleet at the run's clock");
  await expect(fleet).toContainText("297");
  await expect(fleet).toContainText("+2.7%");

  // the ETA board (D-FE-10): the run's rule ETAs, the alerted vessels first, soonest first; the rest on demand
  const board = page.getByRole("table", { name: "ETA by rule for the vessels at sea" });
  await expect(board.locator("tbody tr")).toHaveCount(12);
  await expect(board.locator("tbody tr").first()).toContainText("Containerships Voyager 205");
  await expect(board.locator("tbody tr").first()).toContainText("alert");
  await expect(board.locator('[data-field="eta_in_h"]').first()).toHaveAttribute("data-value", "62.2");
  await page.getByRole("button", { name: "Show all 14 vessels at sea" }).click();
  await expect(board.locator("tbody tr")).toHaveCount(14);
  await expect(board).not.toContainText("Cruise Voyager 600");

  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id),
  ).toEqual([]);
});

test("an earlier run opens from the list; a run without a brief says so", async ({ page }) => {
  await signedIn(page, ops);
  const runs = page.getByRole("list", { name: "Watch runs" });
  await expect(runs.getByRole("link")).toHaveCount(2);
  await runs.getByRole("link", { name: /2026-09-12 12:00Z/ }).click();
  await expect(page).toHaveURL(/\/voyages\/runs\/voyage_watch%3A20260912T1200Z%3A1$/);
  await expect(page.getByRole("list", { name: "Alerts by severity" }).getByRole("listitem")).toHaveCount(2);
  await expect(page.getByText(/No written brief for this run \(skipped no high\)/)).toBeVisible();
  await expect(page.getByLabel("Fleet at the run's clock")).toContainText("295");
  await page.getByRole("link", { name: "Latest run" }).click();
  await expect(page).toHaveURL(/\/voyages$/);
});

test("an unknown run is not found; outside the watch the page is not found", async ({ page }) => {
  await signedIn(page, ops, "/voyages/runs/voyage_watch%3A20250101T0000Z%3A1");
  await expect(page.getByRole("status").filter({ hasText: "No saved watch run" })).toBeVisible();
  await page.context().clearCookies();
  await signedIn(page, finance, "/");
  await expect(page.getByRole("link", { name: "Voyages" })).toHaveCount(0);
  const res = await page.goto("/voyages");
  expect(res?.status()).toBe(404);
});

// Arrival advice web plan: the watch makes the advice for its jit / rta_late alerts; any vessel at sea on demand.
test("a jit alert carries the watch's own arrival advice: the choice, its receipts, the reasons and every option", async ({
  page,
}) => {
  await signedIn(page, ops);
  const row = page
    .getByRole("list", { name: "Alerts by severity" })
    .getByRole("listitem")
    .filter({ hasText: "Dry Bulk Voyager 118" });
  await expect(row).toContainText("Arrival timing");
  const advice = row.getByRole("group", { name: "Arrival advice" });
  await expect(advice).toContainText("Slow down, arrive just in time");
  await expect(advice).toContainText("11.2 kn");
  await expect(advice).toContainText("-14.3 t"); // the one line: choice, speed, arrival, fuel
  await expect(advice).not.toContainText("2026-09-19 01:00Z"); // the rest is folded until asked
  await expect(advice.getByRole("table")).toHaveCount(0);
  await advice.getByRole("button", { name: "Details" }).click();
  await expect(advice).toContainText("2026-09-19 01:00Z"); // the requested time
  await expect(advice.getByRole("button", { name: /14\.3 t/ })).toBeVisible(); // a receipt from the API's span
  await expect(advice.getByRole("table").locator("tbody tr")).toHaveCount(3);
  await expect(advice.locator('tbody tr[aria-current="true"]')).toContainText(
    "Slow down, arrive just in time",
  );
  const arabic = advice.getByRole("list", { name: "Reasons" }).getByRole("listitem").nth(1);
  await expect(arabic).toHaveAttribute("dir", "auto");
  expect(await arabic.evaluate((el) => getComputedStyle(el).direction)).toBe("rtl");
  await expect(arabic.getByRole("button", { name: /6,078 SDR/ })).toBeVisible();
  await expect(advice.getByRole("link", { name: /Compare routes/ })).toHaveCount(0); // no Cape option here
  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id),
  ).toEqual([]);
});

test("any vessel at sea can be advised on demand: prefilled from the ETA board, steps, then its own page", async ({
  page,
}) => {
  await signedIn(page, ops);
  const board = page.getByRole("region", { name: /ETA board/ });
  const first = board.locator("tbody tr").first();
  await first.getByRole("link", { name: /Advise arrival/ }).click();
  await expect(page).toHaveURL(/\/voyages\?advise=\d+/);
  const vessel = page.getByLabel("Vessel id");
  await expect(vessel).not.toHaveValue("");
  await page.getByLabel("Requested time (UTC, optional)").fill("2026-09-20T06:00");
  await page.getByRole("button", { name: "Advise arrival", exact: true }).click();
  await expect(page).toHaveURL(/\/voyages\/arrival\/arrival_advice%3A\d+%3A2026-09-13%3A\d+%3A1$/);
  const advice = page.getByRole("group", { name: "Arrival advice" });
  await expect(advice).toContainText("2026-09-20 06:00Z"); // the requested time given
  await expect(advice.getByRole("table").locator("tbody tr")).toHaveCount(3);
  await expect(page.getByRole("list", { name: "Earlier arrival advice" }).getByRole("link")).toHaveCount(1);
  await page.reload();
  await expect(page.getByRole("group", { name: "Arrival advice" })).toContainText("Slow down");
});

test("a bad vessel id is stopped in the form; an asker without the product sees no request card", async ({
  page,
}) => {
  await signedIn(page, ops);
  await page.getByRole("button", { name: "Advise arrival", exact: true }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Give the id of one of our vessels" }),
  ).toBeVisible();
});

test("only the top alerts show at first; the rest wait behind Show more", async ({ page }) => {
  await signedIn(page, ops);
  const items = page.getByRole("list", { name: "Alerts by severity" }).getByRole("listitem");
  await expect(items).toHaveCount(5); // the mock run has 5 (≤ the top 6): no button
  await expect(page.getByRole("button", { name: /more alerts/ })).toHaveCount(0);
  // the advice under an alert is one line until Details opens it
  const advice = page.getByRole("group", { name: "Arrival advice" }).first();
  await expect(advice).toContainText("Slow down, arrive just in time");
  await expect(advice.getByRole("table")).toHaveCount(0);
});
