// Sign-in attempts per client address (Staging readiness plan P8, e2; ADR-071). The API locks one login after five
// wrong passwords in a row; this limit stops one address from trying many logins. In memory, one web process
// (the deployment runs one), so a restart forgets it — the API's lockout stays the durable layer.
//
// On only behind the deployment's proxy (PORTPILOT_TRUST_PROXY=1): the address is then the LAST X-Forwarded-For entry,
// the one Caddy itself appends (Caddy drops a client's own header unless the peer is a trusted proxy). Locally (no
// proxy, loopback only) every request would share one key, so the limit is off and the tests sign in freely.
// Imported by the sign-in route only (server code); no "server-only" import so the logic test can load it in Node.

export const SIGNIN_WINDOW_MS = 10 * 60 * 1000;
export const SIGNIN_MAX_FAILURES = 10;
const MAX_KEYS = 10_000; // a bound on memory: the oldest keys go first

const failures = new Map<string, number[]>();

export function signinLimitEnabled(): boolean {
  return process.env.PORTPILOT_TRUST_PROXY === "1";
}

export function clientKey(req: Request): string | null {
  if (!signinLimitEnabled()) return null;
  const forwarded = req.headers.get("x-forwarded-for");
  const last = forwarded
    ?.split(",")
    .map((part) => part.trim())
    .filter(Boolean)
    .at(-1);
  return last && last.length <= 64 ? last : "unknown";
}

function recent(key: string, now: number): number[] {
  const kept = (failures.get(key) ?? []).filter((t) => now - t < SIGNIN_WINDOW_MS);
  if (kept.length) failures.set(key, kept);
  else failures.delete(key);
  return kept;
}

/** Seconds to wait when this address is over the limit, else 0. */
export function retryAfterSeconds(key: string | null, now = Date.now()): number {
  if (key === null) return 0;
  const kept = recent(key, now);
  if (kept.length < SIGNIN_MAX_FAILURES) return 0;
  const oldest = kept[0] ?? now;
  return Math.max(1, Math.ceil((oldest + SIGNIN_WINDOW_MS - now) / 1000));
}

export function recordFailure(key: string | null, now = Date.now()): void {
  if (key === null) return;
  const kept = recent(key, now);
  kept.push(now);
  failures.delete(key); // re-insert at the end: Map order = least recently failed first
  failures.set(key, kept);
  while (failures.size > MAX_KEYS) {
    const first = failures.keys().next().value;
    if (first === undefined) break;
    failures.delete(first);
  }
}

export function clearFailures(key: string | null): void {
  if (key !== null) failures.delete(key);
}
