// Local-stack flows (Frontend plan §10.4) against the real API over the isolated clone, scripted model: sign-in
// messages and lockout, sign-out, a follow-up understood by code, a refused tool, an upload's verdict, route advice
// without the canal (code only) and the voyage watch.
import path from "node:path";
import { expect, test } from "@playwright/test";
import { ask, person, signIn } from "./people";

test.describe.configure({ mode: "serial" });

async function tryPassword(page: import("@playwright/test").Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

// The API answers a locked login with the same 401 as a wrong password (no account enumeration, ADR-064): the lock
// shows as the right password being refused. "Too many attempts" is the 429 rate limit, a different rule.
test("a wrong password gets one plain message; after five the login is locked, even with the right one", async ({
  page,
}) => {
  const probe = person("lockout");
  const alert = page.locator("[data-slot=alert]");
  // a refused sign-in costs a full password hash on purpose (~4 s, the same for every reason): a wider wait
  for (let i = 0; i < 5; i++) {
    await tryPassword(page, probe.email, "not-the-password-x");
    await expect(alert).toHaveText("Email or password is wrong.", { timeout: 20_000 });
  }
  await tryPassword(page, probe.email, probe.password);
  await expect(alert).toHaveText("Email or password is wrong.", { timeout: 20_000 });
  await expect(page).toHaveURL(/\/login/);
});

test("signing out ends the session at the API", async ({ page, context }) => {
  await signIn(page, person("employee_hr"));
  await page.getByRole("button", { name: /^Account:/ }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect((await context.cookies()).map((c) => c.name)).not.toContain("ng_session");
  await page.goto("/ask");
  await expect(page).toHaveURL(/\/login/);
});

test("a follow-up is understood by code and answered for the new week", async ({ page }) => {
  await signIn(page, person("manager_finance"));
  await ask(page, "How much did PortPilot bill in week 23 of 2025?");
  await expect(page.getByRole("button", { name: /SDR/ }).first()).toBeVisible();
  const first = await page.getByRole("button", { name: /SDR/ }).count();
  await ask(page, "What about week 24?");
  await expect(page.getByText("Understood as").last()).toBeVisible();
  await expect(page.getByText(/week 24 of 2025/).first()).toBeVisible();
  await expect(page.getByRole("button", { name: /SDR/ })).toHaveCount(first * 2);
});

test("an asker outside Finance sees the refused tool and no figures", async ({ page }) => {
  await signIn(page, person("employee_operations"));
  await ask(page, "How much did PortPilot bill in week 23 of 2025?");
  await expect(page.getByText("not part of your access").first()).toBeVisible();
  await expect(page.getByRole("button", { name: /SDR/ })).toHaveCount(0);
});

// The real screening (ADR-042–044): a company document in the PortPilot template is accepted; a file without the
// template's metadata block is not, with its reason. Both files come from Upload_fixtures.py (read only).
const UPLOADS = path.join(process.cwd(), "..", "Data", "processed", "rag", "eval", "uploads", "fixtures");

test("an uploaded company PDF is screened, accepted and listed; a file off the template is refused", async ({
  page,
}) => {
  await signIn(page, person("manager_operations"));
  const chips = page.getByRole("list", { name: "Attached documents" });
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Attach documents" }).click();
  await (
    await chooser
  ).setFiles([path.join(UPLOADS, "clean_D1.pdf"), path.join(UPLOADS, "inj_metadata_block.pdf")]);
  await expect(chips.locator('li[data-state="accepted"]')).toHaveCount(1, { timeout: 90_000 });
  await expect(chips.getByText("Not accepted").first()).toBeVisible({ timeout: 90_000 });
  await expect(page).toHaveURL(/\/ask\/[0-9a-f-]{36}$/);
  await expect(
    page
      .getByRole("region", { name: "Documents in this conversation" })
      .getByText(/Reefer/)
      .first(),
  ).toBeVisible();
});

test("route advice without the canal is computed by code and says there is nothing to compare", async ({
  page,
}) => {
  await signIn(page, person("employee_operations"), "/routes");
  await page.getByLabel("Origin (UN/LOCODE)").fill("GRPIR");
  await page.getByLabel("Destination (UN/LOCODE)").fill("ITGOA");
  await page.getByText("A vessel type").click();
  await page.getByLabel("SCNT tons").fill("80000");
  await page.getByRole("button", { name: "Compare Suez and Cape" }).click();
  await expect(
    page.getByText("The Suez Canal is not on this voyage, so there is nothing to compare."),
  ).toBeVisible({ timeout: 60_000 });
});

test("the voyage watch lists the latest run's alerts", async ({ page }) => {
  await signIn(page, person("manager_hr"), "/voyages");
  await expect(page.getByRole("heading", { name: "Voyage watch" })).toBeVisible();
  const alerts = page.getByRole("list", { name: "Alerts by severity" }).getByRole("listitem");
  await expect(alerts.first()).toBeVisible();
  expect(await alerts.count()).toBeGreaterThan(0);
});
