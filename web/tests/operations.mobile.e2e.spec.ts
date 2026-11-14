// F6 at phone width: route advice and the voyage watch fit the screen (no sideways scroll), axe 0 serious / critical.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import fixtures from "./fixtures/users.json" with { type: "json" };

const ops = fixtures.users.find((u) => u.email === "ops.employee@portpilot.test")!;

test.describe.configure({ mode: "serial" });
test.skip(({ isMobile }) => !isMobile, "the phone-width check runs on the mobile project");

async function fits(page: Page) {
  const { scroll, client } = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(scroll).toBeLessThanOrEqual(client);
  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id),
  ).toEqual([]);
}

test("route advice and the voyage watch fit a phone", async ({ page }) => {
  const advice = "/routes/route_advice%3A41%3A2026-09-13%3ACNSHA-NLRTM%3A1";
  await page.goto(`/login?next=${encodeURIComponent(advice)}`);
  await page.getByLabel("Work email").fill(ops.email);
  await page.getByLabel("Password").fill(ops.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("region", { name: "Via Suez" })).toContainText("Recommended");
  await fits(page);
  await page.goto("/voyages");
  await expect(page.getByRole("list", { name: "Alerts by severity" }).getByRole("listitem")).toHaveCount(5);
  await expect(page.getByRole("list", { name: "The brief" })).toBeVisible();
  await fits(page);
});
