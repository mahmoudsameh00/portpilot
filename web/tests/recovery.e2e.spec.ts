import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import fixtures from "./fixtures/users.json" with { type: "json" };

const KEY = "portpilot:pending-runs:v1";
const PACK = "/packs/weekly_pack%3Alive%3A2025-W45%3A1";
async function login(page: Page, path: string, ops = false) {
  const user = fixtures.users[ops ? 1 : 0]!;
  await page.goto(`/login?next=${encodeURIComponent(path)}`);
  await page.getByLabel("Work email").fill(user.email);
  await page.getByLabel("Password").fill(user.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL((url) => decodeURIComponent(url.pathname) === decodeURIComponent(path));
  await expect
    .poll(() => page.evaluate((key) => JSON.parse(sessionStorage.getItem(key) ?? "{}").owner, KEY))
    .toBe(user.me.employee_id);
}

for (const kind of ["ask", "ask_ar", "route", "view", "pack_request", "pack_decision"] as const) {
  test(`${kind}: reload recovers an accepted run without a second submission`, async ({ page }, info) => {
    const path = kind.startsWith("ask")
      ? "/ask"
      : kind === "route"
        ? "/routes"
        : kind === "view"
          ? "/views"
          : PACK;
    const posts: string[] = [];
    page.on("request", (request) => {
      if (
        request.method() === "POST" &&
        /\/bff\/(conversations\/[^/]+\/questions|route-advice|views|packs\/)/.test(request.url())
      )
        posts.push(request.url());
    });
    let hold = true;
    const fake = {
      run_id: "recovery-pack",
      kind,
      state: "done",
      thread_id: decodeURIComponent(PACK.slice(7)),
      conversation_id: null,
      created_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
      error: null,
      events: [],
      result: {
        status: kind === "pack_request" ? "proposed" : "published",
        answer:
          kind === "pack_request"
            ? { understood: "Make the summary clearer", steps: [], draft_sha: "fixture" }
            : null,
      },
    };
    if (kind.startsWith("pack_")) {
      // The mock holds one pack and packs.e2e decides it in another worker: this spec reads the view of a pack that
      // still waits (a read-only mock hook), so it neither depends on that state nor changes it.
      await page.route("**/bff/packs/weekly_pack*", async (route) => {
        const token = (await page.context().cookies()).find((c) => c.name === "ng_session")?.value ?? "";
        const fresh = await page.request.get("http://127.0.0.1:8765/__mock/pack-fresh", {
          params: { token },
        });
        await route.fulfill({ json: await fresh.json() });
      });
      await page.route(`**/bff/packs/*/${kind === "pack_request" ? "request" : "decision"}`, (route) =>
        route.fulfill({
          status: 202,
          json: {
            run_id: fake.run_id,
            thread_id: fake.thread_id,
            events_url: "/api/v1/runs/recovery-pack/events",
            run_url: "/api/v1/runs/recovery-pack",
          },
        }),
      );
    }
    await page.route("**/bff/runs/*/events", (route) => route.fulfill({ status: 503 }));
    await page.route(/\/bff\/runs\/[^/]+$/, async (route) => {
      if (hold) return route.fulfill({ json: { state: "running", events: [] } });
      if (kind.startsWith("pack_")) return route.fulfill({ json: fake });
      return route.continue();
    });
    await login(page, path, kind === "route");
    if (kind.startsWith("ask")) {
      await page
        .getByRole("textbox", { name: "Ask PortPilot" })
        .last()
        .fill(kind === "ask_ar" ? "كام إجمالي الفواتير في الأسبوع 23؟" : "How much was billed in week 23?");
      await page.getByRole("button", { name: "Ask", exact: true }).click();
    } else if (kind === "route") {
      await page.getByLabel("Origin (UN/LOCODE)").fill("CNSHA");
      await page.getByLabel("Destination (UN/LOCODE)").fill("NLRTM");
      await page.getByLabel("Vessel id").fill("12");
      await page.getByRole("button", { name: "Compare Suez and Cape" }).click();
    } else if (kind === "view") {
      await page.getByRole("textbox", { name: "Ask for a chart" }).fill("Billed by category in week 23");
      await page.getByRole("button", { name: "Draw it" }).click();
    } else if (kind === "pack_request") {
      await page.getByLabel(/Say what to change/).fill("Make the summary clearer");
      await page.getByRole("button", { name: "Understand my request" }).click();
    } else {
      await page.getByRole("button", { name: "Approve the whole pack" }).click();
      await page.getByRole("button", { name: "Yes, approve the whole pack" }).click();
    }
    await expect
      .poll(() => page.evaluate((key) => JSON.parse(sessionStorage.getItem(key) ?? "{}").runs?.length, KEY))
      .toBe(1);
    const stored = await page.evaluate((key) => JSON.parse(sessionStorage.getItem(key)!), KEY);
    expect(Object.keys(stored.runs[0]).sort()).toEqual(["id", "path"]);
    await page.reload();
    hold = false;
    const recovery = page.getByRole("region", { name: "Recover accepted request" });
    await expect(recovery).toBeVisible();
    await recovery.getByRole("button", { name: "Resume progress" }).click();
    await expect(recovery.getByRole("status")).toHaveText("Result recovered.");
    expect(posts).toHaveLength(1);
    if (kind.startsWith("ask")) {
      await expect(recovery.getByRole("button", { name: /8,394,785/ })).toBeVisible();
      if (kind === "ask_ar")
        await expect(
          recovery
            .locator('[dir="auto"]')
            .filter({ hasText: /[\u0600-\u06ff]/ })
            .first(),
        ).toBeVisible();
    }
    if (kind === "view") {
      await recovery.getByText("Show the numbers", { exact: true }).click();
      await expect(recovery.getByRole("table")).toBeVisible();
    }
    if (kind === "route")
      await expect(recovery.getByRole("link", { name: "Open saved page" })).toHaveAttribute(
        "href",
        /\/routes\/route_advice/,
      );
    if (kind === "pack_request") {
      await expect(recovery).toContainText("Nothing was applied");
      await expect(recovery.getByRole("button", { name: "Confirm" })).toHaveCount(0);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(
      0,
    );
    const axe = await new AxeBuilder({ page }).analyze();
    expect(axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical")).toEqual([]);
    if (kind === "ask_ar")
      await page.screenshot({
        path: `../Notebooks/_scratch/recovery-${info.project.name}.png`,
        fullPage: true,
      });
    await recovery.getByRole("button", { name: "Dismiss reminder" }).click();
    await expect(recovery).toHaveCount(0);
  });
}

test("expired run offers saved history; another account cannot load the reminder", async ({ page }) => {
  await login(page, "/ask");
  await page.evaluate(
    (key) =>
      sessionStorage.setItem(key, JSON.stringify({ owner: 13, runs: [{ id: "expired", path: "/ask" }] })),
    KEY,
  );
  await page.reload();
  const recovery = page.getByRole("region", { name: "Recover accepted request" });
  await recovery.getByRole("button", { name: "Resume progress" }).click();
  await expect(recovery).toContainText("Progress is no longer available");
  await page.evaluate(
    (key) =>
      sessionStorage.setItem(
        key,
        JSON.stringify({ owner: 41, runs: [{ id: "another-account", path: "/routes" }] }),
      ),
    KEY,
  );
  const reads: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("another-account")) reads.push(request.url());
  });
  await page.reload();
  await expect
    .poll(() => page.evaluate((key) => JSON.parse(sessionStorage.getItem(key) ?? "{}").owner, KEY))
    .toBe(13);
  await expect(recovery).toHaveCount(0);
  expect(reads).toEqual([]);
});
