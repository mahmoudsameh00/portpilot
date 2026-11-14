// F3: the Ask page on assistant-ui, against the mock API (runs with SSE events, history, uploads).
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import fixtures from "./fixtures/users.json" with { type: "json" };

const [finance, ops] = fixtures.users as [(typeof fixtures.users)[0], (typeof fixtures.users)[0]];

test.describe.configure({ mode: "serial" });
test.skip(({ isMobile }) => isMobile, "the chat flow runs once, on desktop");

async function signedIn(page: Page, user: { email: string; password: string }) {
  await page.goto("/login?next=%2Fask");
  await page.getByLabel("Work email").fill(user.email);
  await page.getByLabel("Password").fill(user.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/ask$/);
}

async function ask(page: Page, question: string) {
  // the composer listens only once React has hydrated; the API badge leaving "Checking API" proves it
  await expect(page.getByRole("status")).toHaveText(/API (ready|degraded|offline)/);
  const box = page.getByRole("textbox", { name: "Ask PortPilot" }).last();
  await box.fill(question);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
}

test("a question streams its trace, then an answer whose numbers carry receipts", async ({ page }) => {
  await signedIn(page, finance);
  await expect(page.getByRole("heading", { name: "Ask about any number" })).toBeVisible();
  await ask(page, "How much did PortPilot bill in week 23 of 2025?");
  await expect(page).toHaveURL(/\/ask\/[0-9a-f-]{36}$/);
  await expect(page.getByText("Understood as")).toBeVisible();
  const chip = page.getByRole("button", { name: /8,394,785\.98 SDR/ });
  await expect(chip).toBeVisible();
  await expect(page.getByRole("button", { name: /8,120,000\.00 SDR/ })).toBeVisible();
  await chip.click();
  const slip = page.getByRole("dialog");
  await expect(slip).toContainText("billed_sdr");
  await expect(slip).toContainText("finance.kpi_weekly");
  await expect(slip).toContainText("report_week = 23");
  await page.keyboard.press("Escape");
  await page.getByText("How we know").click();
  await expect(page.locator("details").getByText("insight.c1")).toBeVisible();

  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id),
  ).toEqual([]);
});

test("an Arabic follow-up is answered in Arabic, right to left, and the history reloads with its receipts", async ({
  page,
}) => {
  await signedIn(page, finance);
  await ask(page, "How much did PortPilot bill in week 23 of 2025?");
  await expect(page.getByRole("button", { name: /8,394,785\.98 SDR/ })).toBeVisible();
  await ask(page, "وكام كانت الموازنة؟");
  const arabic = page.getByText(/فوترت PortPilot/);
  await expect(arabic).toBeVisible();
  expect(await arabic.evaluate((el) => getComputedStyle(el.closest("p") ?? el).direction)).toBe("rtl");

  const url = page.url();
  await page.goto(url);
  await expect(page.getByText("How much did PortPilot bill in week 23 of 2025?")).toBeVisible();
  await expect(page.getByText(/فوترت PortPilot/)).toBeVisible();
  await expect(page.getByRole("button", { name: /8,394,785\.98 SDR/ })).toHaveCount(2);
  await expect(page.getByRole("navigation", { name: "Conversations" }).getByRole("link")).not.toHaveCount(1);
});

test("an asker outside Finance sees the refused tool and no figures", async ({ page }) => {
  await signedIn(page, ops);
  await ask(page, "How much did PortPilot bill in week 23 of 2025?");
  await expect(page.getByText("not part of your access").first()).toBeVisible();
  await expect(page.getByText("This question is about data outside your access.")).toBeVisible();
  await expect(page.getByRole("button", { name: /SDR/ })).toHaveCount(0);
});

test("a document upload shows the verdict and joins the conversation's documents", async ({ page }) => {
  await signedIn(page, finance);
  await ask(page, "How much did PortPilot bill in week 23 of 2025?");
  await expect(page.getByRole("button", { name: /8,394,785\.98 SDR/ })).toBeVisible();
  await page.getByLabel("Upload a document").setInputFiles({
    name: "berth.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4 test"),
  });
  await expect(page.getByText("Accepted", { exact: true })).toBeVisible();
  await expect(page.getByText("Berth schedule")).toBeVisible();
  await expect(page.getByRole("button", { name: "Ask to add to the library" })).toBeVisible();
});
