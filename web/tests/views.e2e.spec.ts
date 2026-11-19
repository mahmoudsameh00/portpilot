// F5: Charts (a choice from the catalogue, a question, an ask-back) and the pack's chart / analysis edits, on the mock.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import fixtures from "./fixtures/users.json" with { type: "json" };

const user = (email: string) => fixtures.users.find((u) => u.email === email)!;
const manager = user("finance.manager@portpilot.test");
const ops = user("ops.employee@portpilot.test");

test.describe.configure({ mode: "serial" });
test.skip(({ isMobile }) => isMobile, "the charts flow runs once, on desktop");

async function signedIn(page: Page, u: { email: string; password: string }, next: string) {
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Work email").fill(u.email);
  await page.getByLabel("Password").fill(u.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((url) => decodeURIComponent(url.href).endsWith(decodeURIComponent(next)));
  await expect(page.getByRole("status")).toHaveText(/API (ready|degraded|offline)/); // hydrated
}

test("a chosen trend is drawn with the API's caption, a gap for a missing week, and its numbers as a table", async ({
  page,
}) => {
  await signedIn(page, manager, "/views");
  await expect(
    page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Charts" }),
  ).toBeVisible();
  await page.getByLabel("Week of 2025").selectOption("23");
  await page.getByRole("button", { name: "Draw the chart" }).click();
  await expect(page.getByText("Billed and Budget, 13 weeks to 2025-W23")).toBeVisible();
  await expect(page.getByRole("img", { name: /Billed and Budget/ })).toBeVisible();
  await expect(page.getByText("finance.kpi_weekly_trend — report_week = 23")).toBeVisible();
  await page.getByText("Show the numbers").click();
  const cells = page.locator("td[data-value]");
  await expect(cells.first()).toHaveAttribute("data-value", "8000000");
  await expect(page.locator("tbody tr").nth(2).locator("td").first()).toHaveText("—");
  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id),
  ).toEqual([]);
});

test("a question naming a week is drawn; without a week the API asks back", async ({ page }) => {
  await signedIn(page, manager, "/views");
  await page.getByLabel("Ask for a chart").fill("Billed vs budget % by category for week 23, top 5");
  await page.getByRole("button", { name: "Draw it" }).click();
  await expect(page.getByText("By vessel category, 2025-W23")).toBeVisible();
  await page.getByLabel("Ask for a chart").fill("Show the receivables trend");
  await page.getByRole("button", { name: "Draw it" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Which week of 2025" })).toBeVisible();
});

test("outside Finance there is no Charts page", async ({ page }) => {
  await signedIn(page, ops, "/ask");
  await expect(page.getByRole("navigation", { name: "Main" }).getByText("Charts")).toHaveCount(0);
  const res = await page.goto("/views");
  expect(res?.status()).toBe(404);
});
