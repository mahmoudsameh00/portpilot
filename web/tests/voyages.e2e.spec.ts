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
