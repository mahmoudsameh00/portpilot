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
  // no uploads product → no "+" in the composer (the API would refuse the upload anyway)
  await expect(page.getByRole("button", { name: "Attach documents" })).toHaveCount(0);
});

// --- D-FE-11: documents attached from the composer's "+", from the first message on ---------------------------------
const pdf = (name: string, bytes = 13) => ({
  name,
  mimeType: "application/pdf",
  buffer: Buffer.alloc(bytes, "%PDF-1.4 test"),
});
const DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

async function attach(page: Page, files: { name: string; mimeType: string; buffer: Buffer }[]) {
  await expect(page.getByRole("status")).toHaveText(/API (ready|degraded|offline)/); // hydrated
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Attach documents" }).click();
  const picked = await chooser;
  expect(picked.isMultiple()).toBe(true);
  await picked.setFiles(files);
}

const chips = (page: Page) => page.getByRole("list", { name: "Attached documents" }).getByRole("listitem");
// by state, not by words: "Not accepted" contains "accepted"
const accepted = (page: Page) =>
  page.getByRole("list", { name: "Attached documents" }).locator('li[data-state="accepted"]');
const panel = (page: Page) => page.getByRole("region", { name: "Documents in this conversation" });

/** "+" sits before the question box and Send after it (the interface is left to right, also for Arabic text). */
async function plusIsAtTheLeft(page: Page) {
  const x = async (role: "button" | "textbox", name: string) =>
    (await page.getByRole(role, { name, exact: true }).last().boundingBox())?.x ?? -1;
  const [plus, box, send] = [
    await x("button", "Attach documents"),
    await x("textbox", "Ask PortPilot"),
    await x("button", "Ask"),
  ];
  expect(plus).toBeGreaterThanOrEqual(0);
  expect(plus).toBeLessThan(box);
  expect(box).toBeLessThan(send);
}

test("a new conversation's first message carries the documents attached with +", async ({ page }) => {
  await signedIn(page, finance);
  await expect(page.getByRole("heading", { name: "Ask about any number" })).toBeVisible();
  await plusIsAtTheLeft(page);
  const box = page.getByRole("textbox", { name: "Ask PortPilot" }).last();
  await expect(page.getByRole("status")).toHaveText(/API (ready|degraded|offline)/);
  await box.fill("What does the berth schedule say about week 23?");

  // before any question: the pick opens the conversation and uploads at once; Send waits for the verdicts
  await attach(page, [
    pdf("berth.pdf"),
    { name: "tariff-note.docx", mimeType: DOCX, buffer: Buffer.from("PK") },
  ]);
  await expect(chips(page)).toHaveCount(2);
  await expect(page.getByText("Checking the document…").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Ask", exact: true })).toBeDisabled();
  await expect(accepted(page)).toHaveCount(2);
  await expect(page).toHaveURL(/\/ask\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { name: "Ask about any number" })).toBeVisible(); // nothing asked yet
  await expect(panel(page).getByText("Berth schedule")).toBeVisible();
  await expect(panel(page).getByText("tariff-note")).toBeVisible();

  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id),
  ).toEqual([]);

  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const sent = page.getByRole("list", { name: "Documents attached with this question" });
  await expect(sent.getByRole("listitem")).toHaveText(["berth.pdf", "tariff-note.docx"]);
  await expect(chips(page)).toHaveCount(0);
  await expect(page.getByRole("button", { name: /8,394,785\.98 SDR/ })).toBeVisible(); // the run answered
  await expect(panel(page).getByRole("button", { name: "Ask to add to the library" })).toHaveCount(2);

  // a reload keeps the conversation and its documents (the API's list)
  await page.goto(page.url());
  await expect(page.getByText("What does the berth schedule say about week 23?")).toBeVisible();
  await expect(panel(page).getByText("Berth schedule")).toBeVisible();
});

test("an Arabic first question with a document: + stays at the left, the text runs right to left", async ({
  page,
}) => {
  await signedIn(page, finance);
  await attach(page, [pdf("جدول الأرصفة.pdf")]);
  await expect(accepted(page)).toHaveCount(1);
  await expect(chips(page)).toContainText("جدول الأرصفة.pdf");
  const box = page.getByRole("textbox", { name: "Ask PortPilot" }).last();
  await box.fill("فوترنا كام في أسبوع 23 من 2025؟");
  expect(await box.evaluate((el) => getComputedStyle(el).direction)).toBe("rtl");
  await plusIsAtTheLeft(page);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(
    page.getByRole("list", { name: "Documents attached with this question" }).getByRole("listitem"),
  ).toHaveText(["جدول الأرصفة.pdf"]);
  const arabic = page.getByText(/فوترت PortPilot/);
  await expect(arabic).toBeVisible();
  expect(await arabic.evaluate((el) => getComputedStyle(el.closest("p") ?? el).direction)).toBe("rtl");
});

test("a refused document says why, the comfort checks stop a wrong file, and a chip can be removed", async ({
  page,
}) => {
  await signedIn(page, finance);
  await attach(page, [
    pdf("refused-policy.pdf"), // the API refuses it (422 + the reason)
    { name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("x") }, // never sent
    pdf("huge.pdf", 5 * 1024 * 1024 + 1), // never sent
    pdf("screened-memo.pdf"), // accepted, one section removed by the screening
  ]);
  await expect(chips(page)).toHaveCount(4);
  const chip = (name: string) => chips(page).filter({ hasText: name });
  await expect(chip("refused-policy.pdf")).toContainText(
    "Not accepted — Not accepted: the company template header is missing.",
  );
  await expect(chip("notes.txt")).toContainText("Only PDF or Word (.docx) files can be attached.");
  await expect(chip("huge.pdf")).toContainText("This file is larger than 5 MB.");
  await expect(chip("screened-memo.pdf")).toContainText("Accepted — 1 section(s) removed by the screening");
  await expect(panel(page).getByRole("listitem")).toHaveCount(1); // only the accepted one joined
  await expect(panel(page)).toContainText("1 section(s) removed by the screening.");

  await page.getByRole("button", { name: "Remove refused-policy.pdf" }).click();
  await expect(chips(page)).toHaveCount(3);
  // removing an accepted document takes it out of the conversation too
  await page.getByRole("button", { name: "Remove screened-memo.pdf" }).click();
  await expect(chips(page)).toHaveCount(2);
  await expect(panel(page).getByText("No document in this conversation yet.")).toBeVisible();

  await ask(page, "How much did PortPilot bill in week 23 of 2025?");
  await expect(page.getByRole("button", { name: /8,394,785\.98 SDR/ })).toBeVisible();
  await expect(page.getByRole("list", { name: "Documents attached with this question" })).toHaveCount(0);
});

test("the sixth document of a conversation is stopped before it is sent", async ({ page }) => {
  await signedIn(page, finance);
  await attach(
    page,
    [1, 2, 3, 4, 5, 6].map((n) => pdf(`doc-${n}.pdf`)),
  );
  await expect(chips(page)).toHaveCount(6);
  await expect(accepted(page)).toHaveCount(5);
  await expect(chips(page).filter({ hasText: "doc-6.pdf" })).toContainText(
    "A conversation holds at most 5 documents.",
  );
  await expect(panel(page).getByRole("listitem")).toHaveCount(5);
});
