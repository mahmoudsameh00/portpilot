// F2: sign in, the shell from /me, the API status, sign out — against the mock API (tests/mock-api.mjs).
// Serial: the health switch and the lockout counter live in the one mock process.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import fixtures from "./fixtures/users.json" with { type: "json" };

const MOCK = "http://127.0.0.1:8765";
const [finance, ops] = fixtures.users as [(typeof fixtures.users)[0], (typeof fixtures.users)[0]];

test.describe.configure({ mode: "serial" });
test.skip(({ isMobile }) => isMobile, "auth flow runs once, on desktop");

test.beforeEach(async ({ request }) => {
  await request.post(`${MOCK}/__mock/reset`);
});

async function signIn(page: Page, email: string, password: string, path = "/login") {
  await page.goto(path);
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

async function signedIn(page: Page, user: { email: string; password: string }, path = "/login") {
  await signIn(page, user.email, user.password, path);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/Good (morning|afternoon|evening)\./);
}

test("a signed-out visit goes to sign in, and the page is accessible with its security headers", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  const res = await page.request.get("/login");
  expect(res.headers()["content-security-policy"]).toContain("frame-ancestors 'none'");
  expect(res.headers()["x-frame-options"]).toBe("DENY");
  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id),
  ).toEqual([]);
});

test("a wrong password gets one plain message; the fourth try gets the wait time", async ({ page }) => {
  // its own address: the mock is shared with the other spec files running at the same time
  const probe = "lockout.probe@portpilot.test";
  for (let i = 0; i < 3; i++) {
    await signIn(page, probe, "wrong-password");
    await expect(page.locator("[data-slot=alert]")).toHaveText("Email or password is wrong.");
  }
  await signIn(page, probe, "any-password");
  await expect(page.locator("[data-slot=alert]")).toHaveText("Too many attempts. Try again in 2 minutes.");
});

test("signing in shows the shell built from /me; the token never reaches JavaScript", async ({
  page,
  context,
}) => {
  await signIn(page, finance.email, finance.password);
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/Good (morning|afternoon|evening)\./);
  await expect(page.getByText(`Employee ${finance.me.employee_id}, manager in Finance`)).toBeVisible();

  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByText("Weekly pack")).toBeVisible();
  await expect(nav.getByText("Finance")).toBeVisible();
  await expect(nav.getByText("Voyages")).toHaveCount(0);
  await expect(page.getByRole("status")).toHaveText("API ready");

  // D-FE-11: no "Today" tab; home is the page the PortPilot wordmark opens, from anywhere
  await expect(page.getByRole("link", { name: "Today" })).toHaveCount(0);
  await nav.getByRole("link", { name: "Finance" }).click();
  await expect(page).toHaveURL(/\/finance/);
  await expect(page.getByRole("link", { name: "Today" })).toHaveCount(0);
  await page.getByRole("link", { name: "PortPilot", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Your services" })).toBeVisible();

  const session = (await context.cookies()).find((c) => c.name === "ng_session");
  expect(session?.httpOnly).toBe(true);
  expect(session?.sameSite).toBe("Strict");
  expect(session?.secure).toBe(true);
  const visible = await page.evaluate(() => ({
    cookie: document.cookie,
    local: JSON.stringify(localStorage),
    session: JSON.stringify(sessionStorage),
  }));
  expect(visible.cookie).not.toContain("ng_session");
  expect(visible.cookie).toContain("ng_csrf=");
  expect(visible.local + visible.session).not.toContain(session?.value ?? "missing");

  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id),
  ).toEqual([]);
});

test("another role sees its own products", async ({ page }) => {
  await signIn(page, ops.email, ops.password);
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByText("Voyages")).toBeVisible();
  await expect(nav.getByText("Routes")).toBeVisible();
  await expect(nav.getByText("Weekly pack")).toHaveCount(0);
});

test("the BFF sends the bearer token and never the browser's cookies", async ({ page, request }) => {
  await signedIn(page, finance);
  const me = await page.request.get("/bff/me");
  expect(me.status()).toBe(200);
  expect((await me.json()).employee_id).toBe(finance.me.employee_id);
  const token = (await page.context().cookies()).find((c) => c.name === "ng_session")?.value ?? "";
  const last = await (
    await request.get(`${MOCK}/__mock/last`, { params: { token, path: "/api/v1/me" } })
  ).json();
  expect(last.path).toBe("/api/v1/me");
  expect(last.headers.authorization).toMatch(/^Bearer mock_/);
  expect(last.headers.cookie).toBeUndefined();
});

test("the return path is same-origin only", async ({ page }) => {
  await signIn(page, finance.email, finance.password, "/login?next=%2F%2Fevil.example%2Fsteal");
  await expect(page).toHaveURL("http://localhost:3100/");
});

test("an API that is degraded shows in the badge", async ({ page, request }) => {
  await signedIn(page, finance);
  await request.post(`${MOCK}/__mock/health`, { data: { status: "degraded" } });
  await page.reload();
  await expect(page.getByRole("status")).toHaveText("API degraded");
});

test("signing out revokes the session at the API and clears both cookies", async ({ page, context }) => {
  await signedIn(page, finance);
  const token = (await context.cookies()).find((c) => c.name === "ng_session")?.value;
  await page.getByRole("button", { name: /^Account:/ }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  const names = (await context.cookies()).map((c) => c.name);
  expect(names).not.toContain("ng_session");
  expect(names).not.toContain("ng_csrf");
  const reuse = await page.request.get("http://127.0.0.1:8765/api/v1/me", {
    headers: { authorization: `Bearer ${token}` },
  });
  expect(reuse.status()).toBe(401);
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
});

test("an unknown page is a calm 404", async ({ page }) => {
  const res = await page.goto("/no-such-page");
  expect(res?.status()).toBe(404);
  await expect(page.getByRole("heading", { name: "This page is not on the chart." })).toBeVisible();
  await expect(page.getByRole("link", { name: "Back to home" })).toHaveAttribute("href", "/");
});
