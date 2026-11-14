// F4 + D-FE-9: the weekly pack reviewed and decided, against the mock API (one pack, reset before each test).
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import fixtures from "./fixtures/users.json" with { type: "json" };

const MOCK = "http://127.0.0.1:8765";
const user = (email: string) => fixtures.users.find((u) => u.email === email)!;
const manager = user("finance.manager@portpilot.test");
const employee = user("finance.employee@portpilot.test");
const ops = user("ops.employee@portpilot.test");
const PACK = "/packs/weekly_pack%3Alive%3A2025-W45%3A1";

test.describe.configure({ mode: "serial" });
test.skip(({ isMobile }) => isMobile, "the pack flow runs once, on desktop");
test.beforeEach(async ({ request }) => {
  await request.post(`${MOCK}/__mock/pack-reset`);
});

async function signedIn(page: Page, u: { email: string; password: string }, next = "/packs") {
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Work email").fill(u.email);
  await page.getByLabel("Password").fill(u.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(
    (u) => u.href.endsWith(next) || decodeURIComponent(u.href).endsWith(decodeURIComponent(next)),
  );
}

test("the list opens a pack reviewed slide by slide, with the Validator's note and the deck's chart", async ({
  page,
}) => {
  await signedIn(page, manager);
  await page.getByRole("link", { name: /2025-W45/ }).click();
  await expect(page.getByRole("heading", { name: "2025-W45" })).toBeVisible();
  await expect(page.getByText("Draft for approval")).toBeVisible();
  await page.getByRole("button", { name: /Billing beat the budget/ }).click();
  await expect(page.getByText("Validator V2")).toBeVisible();
  await expect(page.getByRole("img", { name: /chart:trend/ })).toBeVisible();
  await expect(page.getByRole("link", { name: "Preview PowerPoint" })).toHaveAttribute(
    "href",
    /\/bff\/packs\/.+\/preview$/,
  );
  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id),
  ).toEqual([]);
});

test("a request in words is understood, shown, and applied only on Confirm", async ({ page }) => {
  await signedIn(page, manager, PACK);
  await page.getByRole("button", { name: /Billing beat the budget/ }).click();
  await page.getByLabel(/Say what to change/).fill("وضّح إن السنة لحد أسبوع 45 بس");
  await page.getByRole("button", { name: "Understand my request" }).click();
  await expect(page.getByText("Understood as")).toBeVisible();
  await expect(page.getByText(/edit the deck — 1 text edit/)).toBeVisible();
  await expect(page.getByText("(weeks 1–45)")).toHaveCount(0);
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByText("Applied. The deck was checked again.")).toBeVisible();
  await expect(page.getByText(/\(weeks 1–45\)/).first()).toBeVisible();
  // §6.8: the decision run as the weekly_pack graph, its node events lighting the steps
  const graph = page.getByTestId("run-graph");
  await expect(graph).toHaveAttribute("aria-label", /Validator/);
  await expect(graph.getByText("Publisher")).toBeVisible();
  await expect(page.getByText("Run finished")).toBeVisible();
});

test("a proposal for a draft that changed meanwhile is refused as stale", async ({ page }) => {
  await signedIn(page, manager, PACK);
  await page.getByRole("button", { name: /Billing beat the budget/ }).click();
  await page.getByLabel(/Say what to change/).fill("Make bullet 3 clearer");
  await page.getByRole("button", { name: "Understand my request" }).click();
  await expect(page.getByRole("button", { name: "Confirm" })).toBeVisible();
  // someone changes the draft before the confirm (another tab)
  const other = await page.context().newPage();
  const csrf = (await page.context().cookies()).find((c) => c.name === "ng_csrf")?.value ?? "";
  const r = await other.request.post(`/bff/packs/weekly_pack%3Alive%3A2025-W45%3A1/decision`, {
    headers: { origin: "http://localhost:3100", "x-csrf-token": csrf },
    data: {
      decision: "edit",
      draft_sha: "0000000000000001",
      edits: [{ bullet: 2, text: "Billing was above budget." }],
    },
  });
  expect(r.status()).toBe(202);
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "The pack changed" })).toBeVisible();
});

test("a direct approval sends the reviewed version and refuses a stale tab", async ({ page }) => {
  await signedIn(page, manager, PACK);
  await page.getByRole("tab", { name: "Decide" }).click();
  const csrf = (await page.context().cookies()).find((c) => c.name === "ng_csrf")?.value ?? "";
  const edited = await page.request.post(`/bff${PACK}/decision`, {
    headers: { origin: "http://localhost:3100", "x-csrf-token": csrf },
    data: {
      decision: "edit",
      draft_sha: "0000000000000001",
      edits: [{ bullet: 2, text: "Reviewed elsewhere." }],
    },
  });
  expect(edited.status()).toBe(202);
  const posted = page.waitForRequest((r) => r.url().endsWith("/decision") && r.method() === "POST");
  await page.getByRole("button", { name: "Approve the pack", exact: true }).click();
  expect((await posted).postDataJSON().draft_sha).toBe("0000000000000001");
  await expect(page.getByRole("alert").filter({ hasText: "The pack changed" })).toBeVisible();
  // Verify the stale click did not publish the mock pack.
  const response = await page.request.get(`/bff${PACK}`);
  expect((await response.json()).published).toBe(false);
});

test("the browser applies the decision rules before sending; approve publishes", async ({ page }) => {
  await signedIn(page, manager, PACK);
  await page.getByRole("tab", { name: "Edit" }).click();
  await page.getByRole("button", { name: "Save and check again" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "an edit carries" })).toBeVisible();
  await page.getByRole("tab", { name: "Decide" }).click();
  await expect(page.getByRole("button", { name: "Reject" })).toBeDisabled();
  await page.getByRole("button", { name: "Approve the pack" }).click();
  await expect(page.getByText("Approved", { exact: true })).toBeVisible();
  await expect(page.getByText("This pack no longer waits for a decision.")).toBeVisible();
  await page.goto("/packs/report");
  await expect(page.getByText("Published", { exact: true })).toBeVisible();
});

test("a Finance employee reads the pack but has no decision panel", async ({ page }) => {
  await signedIn(page, employee, PACK);
  await expect(page.getByText("Waiting for a Finance manager or the CEO.")).toBeVisible();
  await expect(page.getByRole("tab", { name: "Request" })).toHaveCount(0);
});

test("outside Finance the packs are not found", async ({ page }) => {
  await signedIn(page, ops, "/ask");
  await expect(page.getByRole("heading", { name: "Ask about any number" })).toBeVisible();
  const res = await page.goto("/packs");
  expect(res?.status()).toBe(404);
});

test("the pack's chart can be changed from the catalogue, and the analysis revised with a caveat", async ({
  page,
}) => {
  await signedIn(page, manager, PACK);
  await expect(page.getByRole("status")).toHaveText(/API (ready|degraded|offline)/); // hydrated
  await page.getByRole("tab", { name: "Chart" }).click();
  await page.getByRole("button", { name: "Change the chart" }).click();
  await expect(page.getByText("Sent: edit the deck.")).toBeVisible();
  await page.getByRole("tab", { name: "Revise" }).click();
  await expect(page.getByLabel("Summary point 1")).toHaveValue(
    "Billing beat the budget for the third week running.",
  );
  await page.getByLabel("Add a caveat").fill("Week 53 is not in this year.");
  await page.getByRole("button", { name: "Revise" }).click();
  await expect(page.getByText(/Sent: revise the analysis/)).toBeVisible();
});
