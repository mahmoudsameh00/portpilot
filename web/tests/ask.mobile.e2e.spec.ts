// D-FE-11 at phone width: the composer's "+" attaches a document with the first message (the Documents panel is
// desktop-only, so "+" is the phone's only way in); no sideways scroll, axe 0 serious / critical.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import fixtures from "./fixtures/users.json" with { type: "json" };

const finance = fixtures.users[0]!;

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

test("a phone attaches a document with the first message", async ({ page }) => {
  await page.goto("/login?next=%2Fask");
  await page.getByLabel("Work email").fill(finance.email);
  await page.getByLabel("Password").fill(finance.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/ask$/);
  // hydrated: the API badge is not drawn on a phone, but its text still leaves "Checking API" once React runs
  await expect(page.locator('[role="status"]')).toHaveText(/API (ready|degraded|offline)/);

  const plus = page.getByRole("button", { name: "Attach documents" });
  const size = await plus.boundingBox();
  expect(size?.width).toBeGreaterThanOrEqual(44); // a thumb-sized target
  expect(size?.height).toBeGreaterThanOrEqual(44);
  const chooser = page.waitForEvent("filechooser");
  await plus.click();
  await (
    await chooser
  ).setFiles([
    { name: "berth.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 test") },
    {
      name: "a-very-long-file-name-that-must-not-push-the-page-sideways-on-a-phone-2026-week-23.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 test"),
    },
    { name: "refused-policy.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 test") },
  ]);
  const chips = page.getByRole("list", { name: "Attached documents" }).getByRole("listitem");
  await expect(chips).toHaveCount(3);
  const list = page.getByRole("list", { name: "Attached documents" });
  await expect(list.locator('li[data-state="accepted"]')).toHaveCount(2);
  await expect(list.locator('li[data-state="refused"]')).toHaveCount(1);
  await expect(list.locator('li[data-state="refused"]')).toContainText(
    "the company template header is missing",
  );
  await fits(page);

  await page.getByRole("textbox", { name: "Ask PortPilot" }).last().fill("فوترنا كام في أسبوع 23 من 2025؟");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(
    page.getByRole("list", { name: "Documents attached with this question" }).getByRole("listitem"),
  ).toHaveCount(2);
  await expect(page.getByText(/فوترت PortPilot/)).toBeVisible();
  await fits(page);
});
