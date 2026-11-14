import { expect, test } from "@playwright/test";
import { forgetRun, observeRun, pendingRuns, setRecoveryOwner } from "../src/lib/run-recovery";

const originals = new Map(
  ["window", "sessionStorage"].map((key) => [key, Object.getOwnPropertyDescriptor(globalThis, key)]),
);
let saved = new Map<string, string>();
test.beforeEach(() => {
  saved = new Map();
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { location: { pathname: "/ask/conversation-id" } },
  });
  Object.defineProperty(globalThis, "sessionStorage", {
    configurable: true,
    value: {
      getItem: (key: string) => saved.get(key) ?? null,
      setItem: (key: string, value: string) => saved.set(key, value),
      removeItem: (key: string) => saved.delete(key),
    },
  });
  setRecoveryOwner(null);
});
test.afterEach(() => {
  setRecoveryOwner(null);
  for (const [key, descriptor] of originals) {
    if (descriptor) Object.defineProperty(globalThis, key, descriptor);
    else Reflect.deleteProperty(globalThis, key);
  }
});

test("accepted identifiers survive observation loss; terminal delivery removes the reminder", () => {
  setRecoveryOwner(13);
  const settle = observeRun("run-1");
  expect(pendingRuns()).toEqual([]); // already being watched in the mounted screen
  expect(JSON.parse([...saved.values()][0]!)).toEqual({
    owner: 13,
    runs: [{ id: "run-1", path: "/ask/conversation-id" }],
  });
  settle(false);
  expect(pendingRuns()).toHaveLength(1);
  observeRun("run-1")(true);
  expect(pendingRuns()).toEqual([]);
});

test("sign-out and account switching clear identifiers; late completion cannot clear another account", () => {
  setRecoveryOwner(13);
  const late = observeRun("old");
  setRecoveryOwner(null);
  expect(saved.size).toBe(0);
  setRecoveryOwner(41);
  observeRun("new")(false);
  late(true);
  expect(pendingRuns().map((run) => run.id)).toEqual(["new"]);
  forgetRun("new");
  expect(pendingRuns()).toEqual([]);
});

test("disabled browser storage still permits in-page recovery", () => {
  Object.defineProperty(globalThis, "sessionStorage", {
    configurable: true,
    get: () => {
      throw new Error("blocked");
    },
  });
  setRecoveryOwner(13);
  observeRun("run-1")(false);
  expect(pendingRuns().map((run) => run.id)).toEqual(["run-1"]);
});

test("malformed persisted paths never become recovery links", () => {
  saved.set(
    "portpilot:pending-runs:v1",
    JSON.stringify({ owner: 13, runs: [{ id: "run-1", path: "//outside.example" }] }),
  );
  setRecoveryOwner(13);
  expect(pendingRuns()).toEqual([]);
});
