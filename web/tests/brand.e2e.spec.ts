import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("PortPilot identity is readable on light and navy surfaces and has a browser icon", async ({
  page,
}, info) => {
  for (const route of ["/login", "/concept", "/concept/answer"]) {
    await page.goto(route);
    await expect(page).toHaveTitle(/PortPilot/);
    await expect(page.getByText("PortPilot", { exact: true }).filter({ visible: true })).toHaveCount(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(
      0,
    );
    const axe = await new AxeBuilder({ page }).analyze();
    expect(axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
    await page.screenshot({
      path: `../Notebooks/_scratch/portpilot-${info.project.name}-${route.replaceAll("/", "-")}.png`,
      fullPage: true,
    });
  }
  const icon = page.locator('link[rel="icon"][type="image/svg+xml"]');
  await expect(icon).toHaveCount(1);
  const response = await page.request.get((await icon.getAttribute("href"))!);
  expect(response.ok()).toBeTruthy();
  expect(response.headers()["content-type"]).toContain("image/svg+xml");
});
