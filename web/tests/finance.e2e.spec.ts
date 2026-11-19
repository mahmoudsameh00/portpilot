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
    path: `../dev/_scratch/finance-tabs-${info.project.name}.png`,
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

// web dashboards plan (owner 2026-11-15): the Power BI week pages' missing visuals, "Break down by", the export
test("Revenue: break down by any dimension, in any measure, against a compare week; the choice is in the URL", async ({
  page,
}, info) => {
  await signedIn(page, manager, "/finance?week=23&page=revenue");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Dashboards");
  const band = page.getByLabel("Revenue by toll band");
  // amendment 1: three members = one whole in parts → a segmented share bar with the view's shares printed on it
  await expect(band.getByRole("figure", { name: /Billed \(SDR\) by toll band/ })).toBeVisible();
  await expect(band.getByRole("figure").getByText("40.3%").first()).toBeVisible();
  await expect(
    page.getByLabel("Top routes by revenue").getByText("The chart shows the top 10 of 12"),
  ).toBeVisible();
  await band.getByLabel("Break down by").selectOption("credit_rating");
  await band.getByLabel("Measure").selectOption("invoices_billed");
  await band.getByLabel("Compare with").selectOption("22");
  await expect(page).toHaveURL(/rev1\.dim=credit_rating/);
  await expect(page).toHaveURL(/rev1\.m=invoices_billed/);
  await expect(page).toHaveURL(/rev1\.cmp=22/);
  // with a compare week the form switches to ranked bars with a light bar for the other week, and a legend
  await expect(band.getByRole("figure", { name: /Invoices by credit rating/ })).toBeVisible();
  await expect(band.getByRole("figure").getByText("2025-W22")).toBeVisible();
  await band.getByText("Show the numbers").click();
  await expect(band.getByRole("rowheader", { name: "A", exact: true })).toBeVisible();
  // the other cards keep their own choice
  await expect(page.getByLabel("Laden vs ballast").getByLabel("Break down by")).toHaveValue(
    "priced_condition",
  );
  await page.reload();
  await expect(page.getByLabel("Revenue by toll band").getByLabel("Break down by")).toHaveValue(
    "credit_rating",
  );
  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id),
  ).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({
    path: `../dev/_scratch/dashboards-revenue-${info.project.name}.png`,
    fullPage: true,
    animations: "disabled",
  });
});

test("the week pages show Power BI's missing visuals", async ({ page }) => {
  await signedIn(page, manager, "/finance?week=23");
  await expect(page.getByRole("figure", { name: "Billed against budget" })).toBeVisible();
  await expect(page.getByText("Invoices billed")).toBeVisible();
  await page.getByRole("tab", { name: "Receivables" }).click();
  await expect(page.getByRole("img", { name: "DSO — 13 weeks" })).toBeVisible();
  await expect(page.getByText("DSO from late payment")).toBeVisible();
  await expect(page.getByText("MV Nile Star")).toBeVisible();
  await page.getByRole("tab", { name: "Customers" }).click();
  await expect(
    page.getByRole("figure", { name: "Top 10 customers — billed in the last 13 weeks" }),
  ).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Rating" })).toBeVisible();
  await page.getByRole("tab", { name: "Exceptions" }).click();
  await page.getByRole("button", { name: "Year to date" }).click();
  await expect(page.getByText("2 of 41 invoices of the year to date have a finding.")).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Expected (SDR)" })).toBeVisible();
});

test("Export whole page downloads the shown page and week as a workbook", async ({ page }) => {
  await signedIn(page, manager, "/finance?week=23&page=customers");
  const link = page.getByRole("link", { name: "Export whole page" });
  await expect(link).toHaveAttribute("href", "/bff/finance/export?week=23&page=customers");
  const download = page.waitForEvent("download");
  await link.click();
  expect((await download).suggestedFilename()).toBe("PortPilot_dashboard_customers_2025-W23.xlsx");
});

// amendment 1 (owner 2026-11-15): the form follows the data, the item that matters is in colour, every figure exports
test("each page draws its data in the form that fits it and colours what matters", async ({ page }, info) => {
  await signedIn(page, manager, "/finance?week=23");
  // KPI tiles: the change is green when good for the business, orange when bad — with an arrow and a sign
  await expect(page.locator('[data-kpi="billed_sdr"] [data-tone]')).toHaveAttribute("data-tone", "good");
  await expect(page.locator('[data-kpi="overdue_sdr"] [data-tone]')).toHaveAttribute("data-tone", "bad");
  await expect(page.locator('[data-kpi="overdue_sdr"]')).toContainText("+6.3%");
  await expect(page.locator('[data-kind="combo"]')).toBeVisible(); // billed bars + budget / collected lines
  await expect(page.getByText("2025-W23 is the report week; earlier weeks are muted.")).toBeVisible();
  const shot = async (name: string) =>
    page.screenshot({
      path: `../dev/_scratch/dashboards-${name}-${info.project.name}.png`,
      fullPage: true,
      animations: "disabled",
    });
  await shot("overview");
  await page.getByRole("tab", { name: "Revenue" }).click();
  const cats = page.getByRole("figure", { name: "Billing against budget by vessel category" });
  await expect(cats.locator("li[data-below]")).toHaveCount(1); // Tanker billed below its budget, in orange
  await expect(cats.locator("li[data-below]")).toContainText("Tanker");
  const routes = page.getByLabel("Top routes by revenue").getByRole("figure");
  await expect(routes.locator('li[data-emphasis="highlight"]')).toHaveCount(1);
  await expect(routes.locator('li[data-emphasis="highlight"]')).toContainText("EGSUZ-NLRTM");
  await shot("revenue");
  await page.getByRole("tab", { name: "Receivables" }).click();
  await expect(page.getByRole("figure", { name: "Receivables by age" }).getByText("90+ days")).toBeVisible();
  await expect(page.locator('[data-kind="area"]')).toBeVisible();
  await expect(page.getByRole("meter", { name: "Due this week, collected" })).toHaveAttribute(
    "aria-valuenow",
    "64",
  );
  await shot("receivables");
  await page.getByRole("tab", { name: "Customers" }).click();
  const top = page.getByRole("figure", { name: /Top 10 customers/ });
  await expect(top.locator('li[data-emphasis="flag"]')).toContainText("Red Sea Shipping");
  await expect(top.locator('li[data-emphasis="flag"]')).toContainText("watch");
  await shot("customers");
  await page.getByRole("tab", { name: "Exceptions" }).click();
  await expect(page.getByRole("meter", { name: "Invoices with a finding" })).toHaveAttribute(
    "aria-valuenow",
    "2",
  );
  await expect(page.getByText("2 of 41", { exact: true })).toBeVisible();
  await shot("exceptions");
  for (const p of ["receivables", "customers", "exceptions"]) {
    await page.getByRole("tab", { name: p[0]!.toUpperCase() + p.slice(1) }).click();
    await expect(page).toHaveURL(new RegExp(`page=${p}`));
    await expect(page).toHaveTitle(/.+/);
    await expect(
      page
        .getByRole("tabpanel")
        .getByRole("link", { name: /^Download .* as CSV$/ })
        .first(),
    ).toBeVisible();
    const axe = await new AxeBuilder({ page }).analyze();
    expect(
      axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id),
    ).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
});

test("every card downloads its own numbers as Excel or CSV, with the card's own choice", async ({ page }) => {
  await signedIn(page, manager, "/finance?week=23&page=revenue&rev1.dim=route&rev1.cmp=22");
  const cat = page.getByRole("link", { name: "Download Billing against budget by vessel category as CSV" });
  await expect(cat).toHaveAttribute("href", "/bff/finance/export/figure?week=23&figure=category&format=csv");
  const band = page.getByRole("link", { name: "Download Revenue by toll band as Excel" });
  await expect(band).toHaveAttribute(
    "href",
    "/bff/finance/export/figure?week=23&figure=breakdown&format=xlsx&dimension=route&compare=22",
  );
  let download = page.waitForEvent("download");
  await band.click();
  expect((await download).suggestedFilename()).toBe("PortPilot_breakdown_route_2025-W23_vs-W22.xlsx");
  download = page.waitForEvent("download");
  await cat.click();
  expect((await download).suggestedFilename()).toBe("PortPilot_category_2025-W23.csv");
  await expect(page.getByRole("link", { name: "Download Key figures as Excel" })).toHaveAttribute(
    "href",
    "/bff/finance/export/figure?week=23&figure=kpis&format=xlsx&page=revenue",
  );
  // the page workbook stays beside them (owner D-WD-6b)
  await expect(page.getByRole("link", { name: "Export whole page" })).toBeVisible();
  await page.getByRole("tab", { name: "Exceptions" }).click();
  await page.getByRole("button", { name: "Year to date" }).click();
  await expect(page.getByRole("link", { name: "Download Findings as CSV" })).toHaveAttribute(
    "href",
    "/bff/finance/export/figure?week=23&figure=audit_findings&format=csv&ytd=true",
  );
});

test("outside Finance the dashboard is not found", async ({ page }) => {
  await signedIn(page, ops, "/ask");
  const res = await page.goto("/finance");
  expect(res?.status()).toBe(404);
});
