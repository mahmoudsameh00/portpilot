// The audit gate's rules on planted reports (Staging readiness plan, D-S-9): the one reviewed advisory passes while
// its exception holds, and everything else fails.
import { expect, test } from "@playwright/test";
import { auditProblems, blockingAdvisories } from "../scripts/audit-gate.mjs";

const ID = "GHSA-fc5q-39xc-vjpf";
const exceptions = [{ id: ID, package: "picomatch", reviewedLatest: "4.0.7", until: "2026-12-18" }];
const advisory = (name: string, id: string, severity = "high") => ({
  name,
  severity,
  url: `https://github.com/advisories/${id}`,
});
const report = (...via: object[]) => ({
  metadata: { vulnerabilities: { high: via.length } },
  vulnerabilities: {
    "@parcel/watcher": { via: ["picomatch"] },
    picomatch: { via },
  },
});
const check = (r: unknown, today = "2026-11-18", latest: string | null = "4.0.7") =>
  auditProblems(r, { exceptions, today, latestOf: () => latest });

test("the reviewed advisory passes while its exception holds", () => {
  expect(check(report(advisory("picomatch", ID)))).toEqual([]);
  expect(check(report(advisory("picomatch", ID)), "2026-12-18")).toEqual([]);
});

test("a clean report passes", () => {
  expect(check({ metadata: { vulnerabilities: { high: 0 } }, vulnerabilities: {} })).toEqual([]);
});

test("any other high or critical advisory fails", () => {
  expect(check(report(advisory("picomatch", ID), advisory("next", "GHSA-aaaa-bbbb-cccc")))).toEqual([
    "GHSA-aaaa-bbbb-cccc (next) has no exception",
  ]);
  expect(check(report(advisory("next", "GHSA-dddd-eeee-ffff", "critical")))).toHaveLength(1);
});

test("the same advisory id on another package is not covered", () => {
  expect(check(report(advisory("micromatch", ID)))).toEqual([`${ID} (micromatch) has no exception`]);
});

test("a moderate advisory does not block", () => {
  expect(blockingAdvisories(report(advisory("next", "GHSA-gggg-hhhh-iiii", "moderate")))).toEqual([]);
});

test("the exception ends on its date", () => {
  expect(check(report(advisory("picomatch", ID)), "2026-12-19")[0]).toContain(
    "the exception ended on 2026-12-18",
  );
});

test("a newer release of the package ends the exception", () => {
  expect(check(report(advisory("picomatch", ID)), "2026-11-18", "4.0.8")[0]).toContain("upgrade and remove");
  expect(check(report(advisory("picomatch", ID)), "2026-11-18", null)[0]).toContain("version unknown");
});

test("a failed audit never passes", () => {
  expect(check(null)).toEqual(["npm audit returned no report"]);
  expect(check({ error: { code: "ENOTFOUND" } })).toEqual(["npm audit returned no report"]);
});
