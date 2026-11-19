// D-FE-11 on the REAL API, run by hand (not in the CI): documents attached with the composer's "+" from the first
// message of a new conversation, the API's own verdicts on the chips, then a question the document answers.
//   1. the API:   uv run python pipelines/scripts/api/Serve.py        (real models: one question per language)
//   2. the web:   docker compose up -d --build web                    (or npm --prefix web run dev)
//   3. this:      node web/scripts/attach-smoke.mjs [--shots <folder>]
// Reads the Operations employee's test login from web/.env.local (git-ignored; never printed) and the reviewed
// upload fixtures of the upload evaluation (Data/processed/rag/eval/uploads/fixtures). One ✅ / ❌ line per check.
import { mkdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const BASE = process.env.WEB_BASE_URL ?? "http://localhost:3000";
const shots = process.argv.includes("--shots") ? process.argv[process.argv.indexOf("--shots") + 1] : null;
if (shots) mkdirSync(shots, { recursive: true });
const env = Object.fromEntries(
  readFileSync(new URL("../.env.local", import.meta.url), "utf8")
    .split(/\r?\n/)
    .filter((l) => l && !l.startsWith("#") && l.includes("="))
    .map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]),
);
const fixture = (name) =>
  fileURLToPath(new URL(`../../Data/processed/rag/eval/uploads/fixtures/${name}`, import.meta.url));

let failed = 0;
const check = (ok, line) => {
  console.log(`${ok ? "✅" : "❌"} ${line}`);
  if (!ok) failed++;
};
const shot = async (page, name) => {
  if (shots) await page.screenshot({ path: `${shots}/${name}.png` });
};

async function newAsk(browser, viewport) {
  const page = await (await browser.newContext({ viewport })).newPage();
  await page.goto(`${BASE}/login?next=%2Fask`);
  await page.getByLabel("Work email").fill(env.WEB_E2E_EMPLOYEE_OPERATIONS_EMAIL);
  await page.getByLabel("Password").fill(env.WEB_E2E_EMPLOYEE_OPERATIONS_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/ask$/, { timeout: 20_000 });
  await page // hydrated (the badge is not drawn on a phone, its text still changes)
    .locator('[role="status"]')
    .filter({ hasText: /API (ready|degraded|offline)/ })
    .waitFor({ state: "attached", timeout: 20_000 });
  return page;
}

async function attach(page, names) {
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Attach documents" }).click();
  await (await chooser).setFiles(names.map(fixture));
  const list = page.getByRole("list", { name: "Attached documents" });
  await list
    .locator("li")
    .nth(names.length - 1)
    .waitFor({ timeout: 10_000 });
  // the first upload loads the local embedding model: minutes on a cold API, seconds after
  await page.waitForFunction(() => !document.querySelector('li[data-state="uploading"]'), null, {
    timeout: 300_000,
  });
  return list;
}

async function answer(page, question) {
  await page.getByRole("textbox", { name: "Ask PortPilot" }).last().fill(question);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const done = page.getByText("How we know").last();
  // the thread's own alert (Next's route announcer is a role="alert" outside it)
  const broke = page.getByRole("region", { name: "Conversation" }).getByRole("alert").last();
  await Promise.race([done.waitFor({ timeout: 240_000 }), broke.waitFor({ timeout: 240_000 })]);
  const tools = (await page.getByText("search_documents", { exact: true }).count())
    ? ["search_documents"]
    : [];
  const text =
    (await page
      .locator("p.leading-8")
      .last()
      .textContent()
      .catch(() => null)) ?? "";
  if (await done.isVisible()) await done.click();
  const evidence = await page.locator("details ul li").allTextContents();
  return { text, tools, evidence };
}

const browser = await chromium.launch();
try {
  // --- desktop, English: three files with the first message (clean, an attack the screening trims, a refused shape)
  const page = await newAsk(browser, { width: 1440, height: 900 });
  check(true, "signed in as the Operations employee; a new conversation, nothing asked yet");
  const list = await attach(page, ["clean_D1.pdf", "inj_visible_en.pdf", "shape_missing_purpose.docx"]);
  const state = async (name) =>
    (await list.locator("li").filter({ hasText: name }).getAttribute("data-state")) ?? "missing";
  const line = async (name) =>
    ((await list.locator("li").filter({ hasText: name }).textContent()) ?? "").replace(name, "").trim();
  check((await state("clean_D1.pdf")) === "accepted", `clean_D1.pdf: ${await line("clean_D1.pdf")}`);
  check(
    (await state("inj_visible_en.pdf")) === "accepted" &&
      /section\(s\) removed/.test(await line("inj_visible_en.pdf")),
    `inj_visible_en.pdf: ${await line("inj_visible_en.pdf")}`,
  );
  check(
    (await state("shape_missing_purpose.docx")) === "refused",
    `shape_missing_purpose.docx: ${await line("shape_missing_purpose.docx")}`,
  );
  check(
    /\/ask\/[0-9a-f-]{36}$/.test(page.url()),
    "the conversation was opened by the first attached document",
  );
  const listed = page.getByRole("region", { name: "Documents in this conversation" }).getByRole("listitem");
  // the two PDFs are one document (NG-OPS-PRC-0042): the later upload replaces the earlier in the conversation
  const held = await listed.count();
  const heldText = (await listed.first().textContent()) ?? "";
  check(
    held === 1 && /section\(s\) removed by the screening/.test(heldText),
    `the Documents panel lists ${held} document (the same document uploaded twice: the later one replaces it)`,
  );
  await shot(page, "en-1-attached-before-first-message");

  const en = await answer(page, "How soon must a technician record the PTI result in the system?");
  const sent = page
    .getByRole("list", { name: "Documents attached with this question" })
    .getByRole("listitem");
  check((await sent.count()) === 2, `the question's bubble names ${await sent.count()} attached documents`);
  check(
    en.tools.some((t) => t.includes("search_documents")),
    `tools called: ${en.tools.join(", ") || "none"}`,
  );
  check(en.text.length > 0, `answer: ${en.text.slice(0, 220)}`);
  console.log(`   evidence: ${en.evidence.map((e) => e.replace(/\s+/g, " ").trim()).join(" | ") || "none"}`);
  await shot(page, "en-2-answer-uses-the-document");

  // --- phone, Arabic: one document with the first message; "+" at the left, the question right to left
  const phone = await newAsk(browser, { width: 390, height: 844 });
  await attach(phone, ["clean_D1.pdf"]);
  const box = phone.getByRole("textbox", { name: "Ask PortPilot" }).last();
  await box.fill("الفني لازم يسجل نتيجة الفحص في السيستم في خلال قد إيه؟");
  const plusX = (await phone.getByRole("button", { name: "Attach documents" }).boundingBox())?.x ?? -1;
  const boxX = (await box.boundingBox())?.x ?? -1;
  const dir = await box.evaluate((el) => getComputedStyle(el).direction);
  check(
    plusX >= 0 && plusX < boxX && dir === "rtl",
    `phone: "+" at the left (x=${Math.round(plusX)}), the text ${dir}`,
  );
  const fits = await phone.evaluate(
    () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
  );
  check(fits, "phone: no sideways scroll with a chip in the composer");
  await shot(phone, "ar-1-phone-attached-before-first-message");
  const ar = await answer(phone, "الفني لازم يسجل نتيجة الفحص في السيستم في خلال قد إيه؟");
  check(
    ar.tools.some((t) => t.includes("search_documents")),
    `tools called: ${ar.tools.join(", ") || "none"}`,
  );
  check(ar.text.length > 0, `answer: ${ar.text.slice(0, 220)}`);
  await shot(phone, "ar-2-phone-answer");
} catch (error) {
  check(false, `stopped: ${String(error).split("\n")[0]}`);
} finally {
  await browser.close();
}
process.exit(failed ? 1 : 0);
