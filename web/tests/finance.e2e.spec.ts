// F5b (D-FE-7 + D-FE-9): the finance pages in the web, against the mock API.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import fixtures from "./fixtures/users.json" with { type: "json" };

const user = (email: string) => fixtures.users.find((u) => u.email === email)!;
const manager = user("finance.manager@portpilot.test");
const ops = user("ops.employee@portpilot.test");

test.describe.configure({ mode: "serial" });

async function signedIn(page: Page, u: { email: string; password: string }, next: string) {
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Work email").fill(u.email);
  await page.getByLabel("Password").fill(u.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((url) => url.pathname === next.split("?")[0]);
  // hydrated: the API badge left "Checking API". By its text, not by the role alone — Recharts' tooltip is a
  // hidden role="status" too, and the chart can draw before the badge settles (a strict-mode clash under load).
  await expect(
    page.locator('[role="status"]').filter({ hasText: /API (ready|degraded|offline)/ }),
  ).toHaveCount(1);
}

test("Overview: old Smart View bookmarks fall back to KPIs with receipts and the 13-week trend", async ({
  page,
}, info) => {
  await signedIn(page, manager, "/finance?week=23&page=smart");
  await expect(page.getByRole("tab", { selected: true })).toHaveText("Overview");
  await expect(page.getByText("Billing was 3.4% above the week's budget.")).toBeVisible();
  await expect(page.getByText("The largest move on last week: overdue up 6.3%.")).toBeVisible();
  await expect(page.getByRole("img", { name: /Billed, budget and collected/ })).toBeVisible();
  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id),
  ).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(
    await page.getByRole("tablist").evaluate((list) => {
      const bounds = list.getBoundingClientRect();
      return [...list.querySelectorAll('[role="tab"]')].every((tab) => {
        const rect = tab.getBoundingClientRect();
        return rect.top >= bounds.top && rect.bottom <= bounds.bottom;
      });
    }),
  ).toBe(true);
  await page.screenshot({
    path: `../Notebooks/_scratch/finance-tabs-${info.project.name}.png`,
    fullPage: true,
    animations: "disabled",
  });
  const billed = page.getByRole("button", { name: /8\.39M SDR/ });
  await billed.click();
  await expect(page.getByRole("dialog")).toContainText("finance.kpi_weekly");
  await expect(page.getByRole("dialog")).toContainText("billed_sdr");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("every page opens from its tab, and the URL keeps the week and the page", async ({ page }) => {
  await signedIn(page, manager, "/finance?week=23");
  await expect(page.getByRole("tab")).toHaveText([
    "Overview",
    "Revenue",
    "Receivables",
    "Customers",
    "Exceptions",
    "Executive",
  ]);
  await expect(page.getByRole("button", { name: "Draw the chart" })).toHaveCount(0);
  await page.getByRole("tab", { name: "Revenue" }).click();
  await expect(page.getByText(/The biggest driver this week: Container, up/)).toBeVisible();
  await expect(page).toHaveURL(/week=23&page=revenue/);
  await page.getByRole("tab", { name: "Receivables" }).click();
  await expect(page.getByText("The largest part of receivables is current.")).toBeVisible();
  await expect(page.getByText("INV-0004512")).toBeVisible();
  await page.getByRole("tab", { name: "Customers" }).click();
  await expect(page.getByText("1 of the top 2 customers are on the watchlist.")).toBeVisible();
  await page.getByRole("tab", { name: "Exceptions" }).click();
  await expect(page.getByText("2 of 41 invoices of the week have a finding.")).toBeVisible();
  await page.getByRole("tab", { name: "Executive" }).click();
  await expect(page.getByLabel("This week's pack")).toBeVisible();
  await expect(page).toHaveURL(/week=23&page=executive/);
});

test("Executive shows this week's published pack, or says there is none", async ({ page }) => {
  await signedIn(page, manager, "/finance?week=45&page=executive");
  const panel = page.getByLabel("This week's pack");
  await expect(panel.getByText("Billing reached 8,412,300.50 SDR.")).toBeVisible();
  await expect(panel.getByRole("img", { name: "Billed and budget, 13 weeks to 2025-W45" })).toBeVisible();
  await page.getByLabel("Week of 2025").selectOption("44");
  await expect(panel.getByText("No pack has been published for this week yet.")).toBeVisible();
});

test("outside Finance the dashboard is not found", async ({ page }) => {
  await signedIn(page, ops, "/ask");
  const res = await page.goto("/finance");
  expect(res?.status()).toBe(404);
});
