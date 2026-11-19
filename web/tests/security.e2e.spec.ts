// F7 security E2E (Frontend plan §10.5) against the mock API: model text with markup renders inert, nothing leaves
// the origin, and every page carries the CSP (with its nonce), the security headers and axe 0 serious / critical.
// (Token storage, CSRF / cross-origin refusals and the allow-list are covered in auth / bff specs.)
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import fixtures from "./fixtures/users.json" with { type: "json" };

const user = (email: string) => fixtures.users.find((u) => u.email === email)!;
const finance = user("finance.manager@portpilot.test");
const ops = user("ops.employee@portpilot.test");

test.describe.configure({ mode: "serial" });
test.skip(({ isMobile }) => isMobile, "the security sweep runs once, on desktop");

async function signedIn(page: Page, u: { email: string; password: string }, next: string) {
  await page.context().clearCookies();
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Work email").fill(u.email);
  await page.getByLabel("Password").fill(u.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((url) => url.pathname === next);
  await expect(page.getByRole("status").filter({ hasText: /API (ready|degraded|offline)/ })).toBeVisible();
}

test("an answer carrying markup renders as inert text: no script, no image, no link, no request out", async ({
  page,
}) => {
  const outside: string[] = [];
  page.on("request", (r) => {
    const host = new URL(r.url()).host;
    if (!["127.0.0.1:3100", "localhost:3100"].includes(host)) outside.push(host);
  });
  let dialogs = 0;
  page.on("dialog", (d) => {
    dialogs++;
    void d.dismiss();
  });
  await signedIn(page, finance, "/ask");
  await page.getByRole("textbox", { name: "Ask PortPilot" }).last().fill("render test, please");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const answer = page.locator("[dir=auto]").filter({ hasText: "window.__pwned = 1" }).last();
  await expect(answer).toBeVisible();
  // the markup is shown as characters, never parsed
  await expect(answer).toContainText("<script>window.__pwned = 1</script>");
  await expect(answer).toContainText("![chart](https://evil.example/pixel.png)");
  expect(await answer.locator("script, img, a, iframe, object").count()).toBe(0);
  expect(
    await page.locator('a[href^="javascript:"], img[src*="evil.example"], a[href*="evil.example"]').count(),
  ).toBe(0);
  expect(await page.evaluate(() => (window as unknown as { __pwned?: number }).__pwned)).toBeUndefined();
  expect(dialogs).toBe(0);
  expect(outside).toEqual([]);
});

const PAGES: [typeof finance, string][] = [
  ...["/", "/ask", "/packs", "/packs/report", "/views", "/finance"].map(
    (p) => [finance, p] as [typeof finance, string],
  ),
  [ops, "/routes"],
  [ops, "/voyages"],
];

// one test per page (each with its own time budget): the CSP with its nonce, the security headers, axe
for (const [u, path] of PAGES) {
  test(`${path}: CSP with a nonce, the security headers, axe 0 serious / critical`, async ({ page }) => {
    const problems: string[] = [];
    page.on("console", (m) => {
      if (m.type() === "error" && /Content Security Policy|Refused to (execute|load|apply)/i.test(m.text()))
        problems.push(m.text());
    });
    page.on("pageerror", (e) => problems.push(e.message));
    await signedIn(page, u, path);
    const res = await page.reload();
    expect(res?.status()).toBe(200);
    const h = res!.headers();
    expect(h["content-security-policy"]).toMatch(/script-src 'self' 'nonce-[^']+' 'strict-dynamic'/);
    expect(h["content-security-policy"]).toContain("frame-ancestors 'none'");
    expect(h["content-security-policy"]).toContain("object-src 'none'");
    expect(h["x-frame-options"]).toBe("DENY");
    expect(h["x-content-type-options"]).toBe("nosniff");
    expect(h["referrer-policy"]).toBe("no-referrer");
    await expect(page.getByRole("status").filter({ hasText: /API (ready|degraded|offline)/ })).toBeVisible();
    await expect(page.locator("main")).toBeVisible();
    const axe = await new AxeBuilder({ page }).analyze();
    expect(
      axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id),
    ).toEqual([]);
    await page.waitForLoadState("networkidle");
    expect(problems).toEqual([]);
  });
}
