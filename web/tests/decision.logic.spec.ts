// The browser's decision rules = the API's DecisionIn on the same cases (exported by dev/tools/export_approval_cases.py).
import { expect, test } from "@playwright/test";
import fixture from "./fixtures/approval_cases.json" with { type: "json" };
import { decisionProblem } from "../src/lib/decision";

for (const c of fixture.cases) {
  test(`decision rule: ${c.name}`, () => {
    const problem = decisionProblem(c.body as Record<string, unknown>, fixture.limits);
    expect(problem === null, problem ?? "accepted").toBe(c.valid);
  });
}
