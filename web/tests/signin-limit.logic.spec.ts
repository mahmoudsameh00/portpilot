// The BFF's sign-in limit per client address (Staging readiness plan P8, e2): off without the proxy, the proxy's
// own (last) X-Forwarded-For entry as the key, 10 failures in 10 minutes → a wait, a success clears the count.
import { expect, test } from "@playwright/test";
import {
  SIGNIN_MAX_FAILURES,
  SIGNIN_WINDOW_MS,
  clearFailures,
  clientKey,
  recordFailure,
  retryAfterSeconds,
} from "../src/lib/bff/signin-limit";

const saved = process.env.PORTPILOT_TRUST_PROXY;
test.afterEach(() => {
  if (saved === undefined) delete process.env.PORTPILOT_TRUST_PROXY;
  else process.env.PORTPILOT_TRUST_PROXY = saved;
});

const req = (xff?: string) =>
  new Request("http://localhost/bff/login", { headers: xff ? { "x-forwarded-for": xff } : {} });

test("off without the deployment proxy", () => {
  delete process.env.PORTPILOT_TRUST_PROXY;
  const key = clientKey(req("203.0.113.9"));
  expect(key).toBeNull();
  for (let i = 0; i < SIGNIN_MAX_FAILURES * 2; i++) recordFailure(key);
  expect(retryAfterSeconds(key)).toBe(0);
});

test("the proxy's own entry is the key, not the client's", () => {
  process.env.PORTPILOT_TRUST_PROXY = "1";
  expect(clientKey(req("10.0.0.1, 198.51.100.7"))).toBe("198.51.100.7");
  expect(clientKey(req())).toBe("unknown");
});

test("ten failures wait until the window passes; a success clears", () => {
  process.env.PORTPILOT_TRUST_PROXY = "1";
  const key = clientKey(req("192.0.2.44"));
  const t0 = 1_000_000;
  for (let i = 0; i < SIGNIN_MAX_FAILURES - 1; i++) recordFailure(key, t0 + i);
  expect(retryAfterSeconds(key, t0 + 100)).toBe(0);
  recordFailure(key, t0 + 100);
  const wait = retryAfterSeconds(key, t0 + 200);
  expect(wait).toBeGreaterThan(0);
  expect(wait).toBeLessThanOrEqual(SIGNIN_WINDOW_MS / 1000);
  expect(retryAfterSeconds(key, t0 + SIGNIN_WINDOW_MS + 200)).toBe(0); // the window moved past every failure
  for (let i = 0; i < SIGNIN_MAX_FAILURES; i++) recordFailure(key, t0 + 300 + i);
  clearFailures(key);
  expect(retryAfterSeconds(key, t0 + 400)).toBe(0);
});

test("another address is not limited by the first", () => {
  process.env.PORTPILOT_TRUST_PROXY = "1";
  const a = clientKey(req("192.0.2.50"));
  const b = clientKey(req("192.0.2.51"));
  for (let i = 0; i < SIGNIN_MAX_FAILURES; i++) recordFailure(a, 5_000_000 + i);
  expect(retryAfterSeconds(a, 5_000_100)).toBeGreaterThan(0);
  expect(retryAfterSeconds(b, 5_000_100)).toBe(0);
});
