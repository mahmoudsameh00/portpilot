// Local-stack access matrix (Frontend plan §10.4): seven profiles (employee / manager / CEO × Finance / Operations /
// HR) against the real API over the isolated clone. Each sees only its products; a page or a BFF read it may not use
// is refused by the API; nothing of another employee's (a conversation, an answer, a pack) is visible: leakage 0.
import { expect, test, type Page } from "@playwright/test";
import { ask, person, PROFILES, READS_FINANCE, signIn } from "./people";

test.describe.configure({ mode: "serial" });

const FINANCE_PAGES = ["/finance", "/views", "/packs"];
const EVERYONE_PAGES = ["/ask", "/voyages", "/routes"];
const FINANCE_NAV = new Set(["Reports", "Charts", "Dashboards"]);
const ALL_NAV = ["Ask", "Reports", "Charts", "Dashboards", "Voyages", "Routes"];
const DECIDES = new Set(["manager_finance", "ceo_operations"]);
const REFUSED = [403, 404];

const owned = { conversation: "", thread: "", question: "", pack: "" };

async function bff(page: Page, path: string) {
  return page.request.get(`/bff${path}`);
}

test("a Finance employee's question is answered with receipts and is kept as theirs", async ({ page }) => {
  const asker = person("employee_finance");
  await signIn(page, asker);
  // not one of the Ask page's starter questions, so its text on another page can only be a leak
  owned.question = "What did PortPilot bill in week 23 of 2025 against its budget?";
  await ask(page, owned.question);
  await expect(page).toHaveURL(/\/ask\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("button", { name: /SDR/ }).first()).toBeVisible();
  owned.conversation = page.url().split("/").pop() ?? "";
  const detail = await (await bff(page, `/conversations/${owned.conversation}`)).json();
  owned.thread = detail.turns[0].thread_id;
  expect(owned.thread).toMatch(new RegExp(`^ask:${asker.employee_id}:`));
  expect((await bff(page, `/questions/${encodeURIComponent(owned.thread)}`)).status()).toBe(200);
  // a pack thread on the clone, read by a Finance reader, for the pack row of the matrix
  const packs = await (await bff(page, "/packs")).json();
  expect(packs.length).toBeGreaterThan(0);
  owned.pack = packs[0].thread_id;
});

for (const key of PROFILES) {
  test(`${key}: menu, pages and API reads follow ADR-006; another employee's work stays hidden`, async ({
    page,
  }) => {
    const reads = READS_FINANCE[key];
    await signIn(page, person(key));

    const me = await (await bff(page, "/me")).json();
    expect(me.products.packs_read).toBe(reads);
    expect(me.products.packs_decide).toBe(DECIDES.has(key));

    const nav = page.getByRole("navigation", { name: "Main" });
    for (const label of ALL_NAV) {
      const shown = !FINANCE_NAV.has(label) || reads;
      await expect(nav.getByRole("link", { name: label, exact: true })).toHaveCount(shown ? 1 : 0);
    }
    for (const path of EVERYONE_PAGES) expect((await page.goto(path))?.status(), path).toBe(200);
    for (const path of FINANCE_PAGES) {
      const status = (await page.goto(path))?.status();
      if (reads) expect(status, path).toBe(200);
      else expect(REFUSED, `${path} gave ${status}`).toContain(status);
    }

    // the API itself, through the BFF: finance data and packs only for finance readers
    for (const path of ["/finance/weeks", "/packs", `/packs/${encodeURIComponent(owned.pack)}`]) {
      const status = (await bff(page, path)).status();
      if (reads) expect(status, path).toBe(200);
      else expect(REFUSED, `${path} gave ${status}`).toContain(status);
    }
    if (!reads) {
      expect(REFUSED).toContain((await page.goto(`/packs/${encodeURIComponent(owned.pack)}`))?.status());
    }

    // leakage 0: the Finance employee's conversation and answer exist only for them — and for the CEO, who may
    // read every conversation but never continue one (ADR-059 / plan §6a.3; Api_check covers the write refusal)
    if (key === "employee_finance") return;
    if (key === "ceo_operations") {
      const all = await (await bff(page, "/conversations")).json();
      expect(all.map((c: { conversation_id: string }) => c.conversation_id)).toContain(owned.conversation);
      expect((await bff(page, `/conversations/${owned.conversation}`)).status()).toBe(200);
      expect((await bff(page, `/questions/${encodeURIComponent(owned.thread)}`)).status()).toBe(200);
      return;
    }
    const list = await (await bff(page, "/conversations")).json();
    expect(list.map((c: { conversation_id: string }) => c.conversation_id)).not.toContain(owned.conversation);
    const conv = (await bff(page, `/conversations/${owned.conversation}`)).status();
    expect(REFUSED, `conversation gave ${conv}`).toContain(conv);
    const answer = (await bff(page, `/questions/${encodeURIComponent(owned.thread)}`)).status();
    expect(REFUSED, `answer gave ${answer}`).toContain(answer);
    const questions = await (await bff(page, "/questions")).json();
    expect(questions.map((q: { thread_id: string }) => q.thread_id)).not.toContain(owned.thread);
    await page.goto(`/ask/${owned.conversation}`);
    await expect(page.getByRole("status").filter({ hasText: /API (ready|degraded|offline)/ })).toBeVisible();
    await expect(page.getByText(owned.question)).toHaveCount(0);
    await expect(page.getByRole("button", { name: /SDR/ })).toHaveCount(0);
  });
}
