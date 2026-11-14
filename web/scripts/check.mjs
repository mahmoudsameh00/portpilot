// One command, one ✅ line per suite (the project's tools/run.py style, Frontend plan §10).
// Usage: npm run check            (static checks + Playwright against the dev server or a fresh build in CI)
//        npm run check -- --static (static checks only)
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";

const staticOnly = process.argv.includes("--static");
const run = (cmd) =>
  spawnSync(cmd, { shell: true, encoding: "utf8", env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" } });
const allowlist = "src/lib/bff/allowlist.generated.ts";

const suites = [
  [
    "allow-list matches the OpenAPI snapshot",
    () => {
      const before = readFileSync(allowlist, "utf8");
      const r = run("node scripts/gen-allowlist.mjs");
      return r.status === 0 && readFileSync(allowlist, "utf8") === before ? null : "regenerated file differs";
    },
  ],
  [
    "typed client = the OpenAPI snapshot (Orval)",
    () => {
      const files = ["src/api/generated/client.ts", "src/api/generated/zod.ts"];
      const before = files.map((f) => readFileSync(f, "utf8"));
      const r = run("npx orval --config orval.config.ts");
      return r.status === 0 && files.every((f, i) => readFileSync(f, "utf8") === before[i])
        ? null
        : "regenerated client differs";
    },
  ],
  ["typecheck (tsc)", () => (run("npx tsc --noEmit").status === 0 ? null : "tsc failed")],
  [
    "lint (eslint, RTL + no-danger bans)",
    () => (run("npx eslint . --max-warnings 0").status === 0 ? null : "eslint failed"),
  ],
  [
    "format (prettier)",
    () => (run("npx prettier --check .").status === 0 ? null : "prettier --check failed"),
  ],
  [
    "audit (runtime deps, high+)",
    () => (run("npm audit --omit=dev --audit-level=high").status === 0 ? null : "npm audit failed"),
  ],
];
if (!staticOnly)
  suites.push([
    "tests (Playwright: logic, E2E desktop + mobile, auth on the mock API, axe, BFF)",
    () => {
      const r = run("npx playwright test --reporter=line");
      const m = /(\d+) passed/.exec(r.stdout ?? "");
      return r.status === 0 ? null : `failed${m ? ` (${m[1]} passed)` : ""}`;
    },
  ]);

let failed = 0;
for (const [name, fn] of suites) {
  const err = fn();
  console.log(err ? `❌ ${name}: ${err}` : `✅ ${name}`);
  if (err) failed++;
}
process.exit(failed ? 1 : 0);
