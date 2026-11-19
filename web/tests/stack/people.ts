// The local-stack suite's identities (written by dev/checks/api/Web_stack_fixture.py into the git-ignored
// .fixture/ folder at global setup) and the shared sign-in step.
import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, type Page } from "@playwright/test";

export type Person = {
  employee_id: number;
  email: string;
  role: string;
  dept: string;
  password: string;
  key: string;
};

export const FIXTURE = path.join(process.cwd(), "tests", "stack", ".fixture"); // npx runs from web/

export function people(): Person[] {
  return (JSON.parse(readFileSync(path.join(FIXTURE, "people.json"), "utf-8")) as { people: Person[] })
    .people;
}

export function person(key: string): Person {
  const found = people().find((p) => p.key === key);
  if (!found) throw new Error(`no fixture identity ${key}`);
  return found;
}

/** The seven profiles of Api_check Phase 2 (the lockout probe is not one of them). */
export const PROFILES = [
  "employee_finance",
  "manager_finance",
  "employee_operations",
  "manager_operations",
  "employee_hr",
  "manager_hr",
  "ceo_operations",
] as const;

/** ADR-006 by hand (= Api_check Phase 2): who reads finance (Reports, Charts, Dashboards); everyone has Ask,
 * Voyages and Routes. */
export const READS_FINANCE: Record<(typeof PROFILES)[number], boolean> = {
  employee_finance: true,
  manager_finance: true,
  employee_operations: false,
  manager_operations: true,
  employee_hr: false,
  manager_hr: true,
  ceo_operations: true,
};

export async function signIn(page: Page, p: Person, next = "/ask") {
  await page.context().clearCookies();
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Work email").fill(p.email);
  await page.getByLabel("Password").fill(p.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((url) => url.pathname === next);
  await expect(page.getByRole("status").filter({ hasText: /API (ready|degraded|offline)/ })).toBeVisible();
}

export async function ask(page: Page, question: string) {
  const box = page.getByRole("textbox", { name: "Ask PortPilot" }).last();
  await box.fill(question);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
}
