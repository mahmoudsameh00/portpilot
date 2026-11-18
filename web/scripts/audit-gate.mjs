// The runtime dependency audit's verdict (high and critical advisories), kept apart from check.mjs so its rules are
// tested on planted reports (tests/audit-gate.logic.spec.ts).
//
// An exception names ONE advisory that has no patched release, and it ends by itself: on its date, or as soon as the
// package publishes a release newer than the one the advisory was reviewed on. Any other advisory fails the check.
export const AUDIT_EXCEPTIONS = [
  {
    // Owner decision 2026-11-18 (Staging readiness plan, D-S-9). picomatch through 4.0.7 has no patched release. The
    // attack needs a glob pattern chosen by the attacker; web/src never imports picomatch and builds no glob from input.
    id: "GHSA-fc5q-39xc-vjpf",
    package: "picomatch",
    reviewedLatest: "4.0.7",
    until: "2026-12-18",
  },
];

const BLOCKING = new Set(["high", "critical"]);
const advisoryId = (url) =>
  String(url ?? "")
    .split("/")
    .pop();

/** Every blocking advisory in an `npm audit --json` report, as `{ id, package }` (one entry per advisory). */
export function blockingAdvisories(report) {
  const found = new Map();
  for (const entry of Object.values(report.vulnerabilities ?? {})) {
    for (const via of entry.via ?? []) {
      // a string names another package of the report, whose own entry carries the advisory
      if (typeof via === "object" && BLOCKING.has(via.severity)) {
        const id = advisoryId(via.url);
        found.set(id, { id, package: via.name });
      }
    }
  }
  return [...found.values()];
}

/**
 * The problems that fail the check; an empty list passes. It fails closed: a report without audit metadata (a network
 * or registry error) is a problem, never a pass.
 * `latestOf(name)` returns the package's latest published version.
 */
export function auditProblems(report, { exceptions = AUDIT_EXCEPTIONS, today, latestOf }) {
  if (!report || typeof report !== "object" || !report.metadata?.vulnerabilities) {
    return ["npm audit returned no report"];
  }
  const problems = [];
  for (const advisory of blockingAdvisories(report)) {
    const exception = exceptions.find((e) => e.id === advisory.id && e.package === advisory.package);
    if (!exception) {
      problems.push(`${advisory.id} (${advisory.package}) has no exception`);
    } else if (today > exception.until) {
      problems.push(`${advisory.id}: the exception ended on ${exception.until}, review it again`);
    } else {
      const latest = latestOf(exception.package);
      if (latest !== exception.reviewedLatest) {
        problems.push(
          `${advisory.id}: ${exception.package} ${latest ?? "(version unknown)"} is out (reviewed on ` +
            `${exception.reviewedLatest}): upgrade and remove the exception`,
        );
      }
    }
  }
  return problems;
}
