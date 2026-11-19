import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import fixtures from "./fixtures/users.json" with { type: "json" };

const manager = fixtures.users.find((u) => u.email === "finance.manager@portpilot.test")!;
const PACK = "/packs/weekly_pack%3Alive%3A2025-W45%3A1";

for (const screen of ["review", "finance"] as const) {
  test(`${screen}: a pending database sync stays visible while the approved deck remains available`, async ({
    page,
  }, info) => {
    const next = screen === "review" ? PACK : "/finance?week=45&page=executive";
    await page.route(
      screen === "review" ? "**/bff/packs/weekly_pack*" : "**/bff/finance/pack?*",
      async (route) => {
        const response = await route.fetch();
        const data = await response.json();
        await route.fulfill({
          response,
          json: {
            ...data,
            publication_sync: "pending",
            ...(screen === "review"
              ? {
                  published: true,
                  status: "published",
                  next: [],
                  decisions: [],
                  has_preview: false,
                  allowed: { ...data.allowed, decide: false },
                }
              : {}),
          },
        });
      },
    );
    await page.goto(`/login?next=${encodeURIComponent(next)}`);
    await page.getByLabel("Work email").fill(manager.email);
    await page.getByLabel("Password").fill(manager.password);
    await page.getByRole("button", { name: "Sign in" }).click();
    const notice = page.getByRole("status").filter({ hasText: "Power BI synchronization is pending" });
    await expect(notice).toBeVisible();
    await expect(notice).toContainText("approved deck is saved");
    if (screen === "review") {
      await expect(page.getByRole("link", { name: "Published deck" })).toBeVisible();
      await expect(page.getByText("This pack no longer waits for a decision.")).toBeVisible();
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(
      0,
    );
    const axe = await new AxeBuilder({ page }).analyze();
    expect(axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
    await page.screenshot({
      path: `../dev/_scratch/publication-${info.project.name}-${screen}.png`,
      fullPage: true,
    });
  });
}
