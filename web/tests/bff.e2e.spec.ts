import { expect, test } from "@playwright/test";

// The BFF's own rules (plan §4.2–4.3), checked without the API: every case is refused before any upstream call.
test.describe("BFF", () => {
  test.skip(
    ({ browserName, isMobile }) => browserName !== "chromium" || isMobile,
    "request-level checks run once",
  );

  test("a path outside the API's schema is 404", async ({ request }) => {
    expect((await request.get("/bff/admin/users")).status()).toBe(404);
    expect((await request.get("/bff/me/%2e%2e/%2e%2e/etc/passwd")).status()).toBe(404);
    expect((await request.put("/bff/me")).status()).toBe(405);
  });

  test("a known path without a session is 401", async ({ request }) => {
    const res = await request.get("/bff/me");
    expect(res.status()).toBe(401);
    expect(res.headers()["cache-control"]).toContain("no-store");
  });

  test("an unsafe call from another origin, or without the CSRF token, is 403", async ({ request }) => {
    const evil = { origin: "https://evil.example", "content-type": "application/json" };
    expect((await request.post("/bff/conversations", { headers: evil, data: {} })).status()).toBe(403);
    expect(
      (await request.post("/bff/login", { headers: evil, data: { email: "a@b.c", password: "x" } })).status(),
    ).toBe(403);
    const same = { origin: "http://localhost:3100", "content-type": "application/json" };
    expect((await request.post("/bff/conversations", { headers: same, data: {} })).status()).toBe(403);
    expect((await request.post("/bff/logout", { headers: same })).status()).toBe(403);
  });

  test("login validates its body before calling the API", async ({ request }) => {
    const same = { origin: "http://localhost:3100", "content-type": "application/json" };
    expect((await request.post("/bff/login", { headers: same, data: { email: "a" } })).status()).toBe(422);
  });
});
