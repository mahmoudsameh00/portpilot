import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const PAGES = ["/concept", "/concept/answer", "/concept/pack"];

for (const path of PAGES) {
  test(`${path}: English UI, CSP, no sideways scroll, accessibility`, async ({ page }) => {
    const res = await page.goto(path);
    expect(res?.status()).toBe(200);
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");

    const csp = res?.headers()["content-security-policy"] ?? "";
    expect(csp).toMatch(/script-src 'self' 'nonce-[A-Za-z0-9+/=]+' 'strict-dynamic'/);
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
    expect(res?.headers()["x-content-type-options"]).toBe("nosniff");
    expect(res?.headers()["referrer-policy"]).toBe("no-referrer");

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);

    const axe = await new AxeBuilder({ page }).exclude("nextjs-portal").analyze();
    const serious = axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
  });
}

test("an Arabic question gets a right-to-left Arabic answer inside the English UI", async ({ page }) => {
  await page.goto("/concept/answer");
  const arabic = page.getByText(/من فواتير أسبوع 23/);
  await expect(arabic).toBeVisible();
  const direction = await arabic.evaluate((el) => getComputedStyle(el.closest("p") ?? el).direction);
  expect(direction).toBe("rtl");
});

test("a number opens its receipt, and Esc closes it (client JS runs under the CSP)", async ({ page }) => {
  await page.goto("/concept/answer");
  await page.getByRole("button", { name: /8,394,785\.98 SDR/ }).click();
  const slip = page.getByRole("dialog");
  await expect(slip).toContainText("billed_sdr");
  await expect(slip).toContainText("finance.finance_kpi");
  await expect(slip).toContainText("kpi.weekly");
  await page.keyboard.press("Escape");
  await expect(slip).toBeHidden();
});

test("the home map draws the two lanes and the moving vessels", async ({ page }) => {
  await page.goto("/concept");
  const map = page.getByRole("img", { name: /trade lanes/ });
  await expect(map).toBeVisible();
  expect(await map.locator("animateMotion").count()).toBeGreaterThanOrEqual(4);
  await expect(map.getByText("EGPSD")).toBeVisible();
});

test("the pack tabs switch (Radix under the CSP)", async ({ page }) => {
  await page.goto("/concept/pack");
  await page.getByRole("tab", { name: "Note" }).click();
  await expect(page.getByText("Write the approver's note")).toBeVisible();
});

test("the pages cannot be framed", async ({ page }) => {
  const res = await page.goto("/concept");
  expect(res?.headers()["x-frame-options"]).toBe("DENY");
});

test("no CSP violation and no console error", async ({ page }) => {
  const problems: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") problems.push(m.text());
  });
  page.on("pageerror", (e) => problems.push(e.message));
  for (const path of PAGES) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
  }
  expect(problems).toEqual([]);
});
