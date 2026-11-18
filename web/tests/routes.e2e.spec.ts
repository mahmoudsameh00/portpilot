// F6: route advice (plan §6.6) against the mock API — a run with SSE node events → the decision view with receipts;
// earlier advice; the form's own rules; refusals.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import fixtures from "./fixtures/users.json" with { type: "json" };

const MOCK = "http://127.0.0.1:8765";
const user = (email: string) => fixtures.users.find((u) => u.email === email)!;
const ops = user("ops.employee@portpilot.test");
const finance = user("finance.manager@portpilot.test");

test.describe.configure({ mode: "serial" });
test.skip(({ isMobile }) => isMobile, "the route flow runs once, on desktop");
test.beforeEach(async ({ request }) => {
  await request.post(`${MOCK}/__mock/routes-reset`);
});

async function signedIn(page: Page, u: { email: string; password: string }, next = "/routes") {
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Work email").fill(u.email);
  await page.getByLabel("Password").fill(u.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((url) => decodeURIComponent(url.pathname) === decodeURIComponent(next));
  // the form listens only once React has hydrated; the API badge leaving "Checking API" proves it
  await expect(page.getByRole("status").filter({ hasText: /API (ready|degraded|offline)/ })).toBeVisible();
}

test("a port pair streams its steps, then Suez and the Cape side by side with receipts", async ({ page }) => {
  await signedIn(page, ops);
  await expect(page.getByRole("heading", { name: "Route advice" })).toBeVisible();
  await page.getByLabel("Origin (UN/LOCODE)").fill("cnsha");
  await page.getByLabel("Destination (UN/LOCODE)").fill("NLRTM");
  await page.getByLabel("Vessel id").fill("12");
  await page.getByRole("button", { name: "Compare Suez and Cape" }).click();
  await expect(page.getByLabel("What is being done")).toContainText("Pricing fuel and dues");
  await expect(page).toHaveURL(/\/routes\/route_advice%3A41%3A2026-09-13%3ACNSHA-NLRTM%3A2$/);

  const suez = page.getByRole("region", { name: "Via Suez" });
  const cape = page.getByRole("region", { name: "Via the Cape" });
  await expect(suez).toContainText("Recommended");
  await expect(suez).toContainText("610,877.36 SDR");
  await expect(suez).toContainText("98,412.36 SDR");
  await expect(cape).toContainText("676,600.00 SDR");
  await expect(cape).not.toContainText("Recommended");
  await expect(page.getByTestId("saving-line")).toContainText("Via Suez saves 65,722.64 SDR · −10.03 days");
  await expect(page.getByRole("img", { name: /CNSHA to NLRTM.*recommended via Suez/ })).toBeVisible();

  // a number in a reason opens its receipt: field, source, filter
  await page.getByRole("button", { name: /98,412\.36 SDR/ }).click();
  const slip = page.getByRole("dialog");
  await expect(slip).toContainText("suez_dues_sdr");
  await expect(slip).toContainText("route.compare");
  await expect(slip).toContainText("route = suez");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: /65,722\.64 SDR/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /2\.7 %/ })).toBeVisible();

  await page.getByText("How we know").click();
  await expect(page.getByText(/425\.00 SDR per tonne/)).toBeVisible();
  await expect(page.getByText(/suez_toll ok/)).toBeVisible();
  await expect(page.getByText("7 numbers with receipts")).toBeVisible();

  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id),
  ).toEqual([]);
});

test("earlier advice is listed and opens again after a reload", async ({ page }) => {
  await signedIn(page, ops);
  const list = page.getByRole("list", { name: "Earlier advice" });
  await expect(list.getByRole("link")).toHaveCount(1);
  await list.getByRole("link", { name: /CNSHA → NLRTM/ }).click();
  await expect(page).toHaveURL(/CNSHA-NLRTM%3A1$/);
  await page.reload();
  await expect(page.getByRole("region", { name: "Via Suez" })).toContainText("Recommended");
  await expect(page.getByLabel("Origin (UN/LOCODE)")).toHaveValue("CNSHA");
});

test("a voyage without the canal says so, with no comparison to make", async ({ page }) => {
  await signedIn(page, ops);
  await page.getByLabel("Origin (UN/LOCODE)").fill("GRPIR");
  await page.getByLabel("Destination (UN/LOCODE)").fill("ITGOA");
  await page.getByText("A vessel type").click();
  await page.getByLabel("SCNT tons").fill("80000");
  await page.getByRole("button", { name: "Compare Suez and Cape" }).click();
  await expect(
    page.getByText("The Suez Canal is not on this voyage, so there is nothing to compare."),
  ).toBeVisible();
  await expect(page.getByRole("region", { name: "Direct" })).toBeVisible();
  await expect(page.getByTestId("saving-line")).toHaveCount(0);
});

test("the form's own rules stop a request before it is sent", async ({ page }) => {
  await signedIn(page, ops);
  let posted = 0;
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().includes("/bff/route-advice")) posted++;
  });
  await page.getByLabel("Origin (UN/LOCODE)").fill("NLRTM");
  await page.getByLabel("Destination (UN/LOCODE)").fill("NLRTM");
  await page.getByLabel("Vessel id").fill("12");
  await page.getByRole("button", { name: "Compare Suez and Cape" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Origin and destination must differ." }),
  ).toBeVisible();
  await page.getByLabel("Destination (UN/LOCODE)").fill("RTM");
  await page.getByRole("button", { name: "Compare Suez and Cape" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "5-letter UN/LOCODE" })).toBeVisible();
  expect(posted).toBe(0);
});

test("another employee's advice is not found; outside Operations the page is not found", async ({ page }) => {
  await signedIn(page, ops, "/routes/route_advice%3A99%3A2026-09-13%3ACNSHA-NLRTM%3A1");
  await expect(page.getByRole("alert").filter({ hasText: "This advice is not on the chart." })).toBeVisible();
  await page.context().clearCookies();
  await signedIn(page, finance, "/");
  await expect(page.getByRole("link", { name: "Routes" })).toHaveCount(0);
  const res = await page.goto("/routes");
  expect(res?.status()).toBe(404);
});

test("Compare routes from an arrival advice opens route advice with its vessel and destination", async ({
  page,
}) => {
  await signedIn(page, ops);
  await page.goto("/routes?vessel=21&destination=nlrtm");
  await expect(page.getByLabel("Destination (UN/LOCODE)")).toHaveValue("NLRTM");
  await expect(page.getByLabel("Vessel id")).toHaveValue("21");
  await page.goto("/routes?vessel=x1&destination=EVIL'");
  await expect(page.getByLabel("Destination (UN/LOCODE)")).toHaveValue(""); // only a LOCODE and a number are read
  await expect(page.getByLabel("Vessel id")).toHaveValue("");
});
