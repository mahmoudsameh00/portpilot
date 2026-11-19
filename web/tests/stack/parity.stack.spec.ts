// Web dashboards plan Phase 5 (parity, week 17 = the last published pack): the Dashboards page over the real API and
// the full-data clone shows exactly the `finance` views' numbers. The same numbers were read from Power BI by DAX
// (Power BI TMDL editing) and from the views on 2026-11-16: 249 values, 0 differences (the parity table in the plan).
// The web adds no arithmetic (ADR-047): it rounds for display only (formatValue: SDR as M / k, % and days to 0.1).
import { expect, test } from "@playwright/test";
import { person, signIn } from "./people";

const WEEK = 17;
/** finance.kpi_weekly, report_week 17 (= Power BI's measures for the same week) */
const VIEW = {
  billed_sdr: 4951237.35,
  collected_sdr: 5569636.85,
  ar_sdr: 37981157.17,
  overdue_sdr: 9383218.61,
  invoices_billed: 16,
  dso_days: 51.4,
  budget_variance_pct: -12.49,
  billed_wow_pct: 68.71,
  overdue_new_sdr: 2466349.35,
  overdue_paid_sdr: 3333987.67,
} as const;

test("Dashboards week 17: the API returns the view's row and the page shows it, only rounded", async ({
  page,
}) => {
  await signIn(page, person("manager_finance"), "/finance");
  await page.goto(`/finance?week=${WEEK}&page=overview`);
  const api = await page.request.get(`/bff/finance/weekly?week=${WEEK}`);
  expect(api.status()).toBe(200);
  const row = (await api.json()).rows[0];
  for (const [field, value] of Object.entries(VIEW)) expect(row[field], field).toBe(value);

  const tile = (field: string) => page.locator(`[data-kpi="${field}"]`);
  await expect(tile("billed_sdr")).toContainText("4.95M");
  await expect(tile("collected_sdr")).toContainText("5.57M");
  await expect(tile("ar_sdr")).toContainText("37.98M");
  await expect(tile("overdue_sdr")).toContainText("9.38M");
  await expect(tile("dso_days")).toContainText("51.4 d");
  await expect(tile("invoices_billed")).toContainText("16");
  await expect(page.getByText("Billing was 12.5% below the week's budget.")).toBeVisible();

  await page.goto(`/finance?week=${WEEK}&page=receivables`);
  await expect(tile("overdue_new_sdr")).toContainText("2.47M");
  await expect(tile("overdue_paid_sdr")).toContainText("3.33M");
});
