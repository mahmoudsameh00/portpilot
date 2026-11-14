// POST /bff/login (Frontend plan §4.1): the token goes into an httpOnly cookie; the browser gets `me` only.
import { cookies } from "next/headers";
import { z } from "zod";
import {
  CSRF_COOKIE,
  JSON_LIMIT,
  SESSION_COOKIE,
  apiBase,
  cookieOptions,
  newCsrfToken,
  problem,
  sameOrigin,
} from "@/lib/bff/core";

export const dynamic = "force-dynamic";

const LoginIn = z
  .object({ email: z.string().min(3).max(254), password: z.string().min(1).max(1024) })
  .strict();
const TokenOut = z.object({
  token: z.string().min(1),
  expires_at: z.string(),
  me: z.record(z.string(), z.unknown()),
});

export async function POST(req: Request): Promise<Response> {
  // No session yet → no double-submit token; the Origin check + SameSite stop login CSRF.
  if (!sameOrigin(req)) return problem(403, "Request refused");
  const length = Number(req.headers.get("content-length") ?? "NaN");
  if (!Number.isFinite(length) || length > JSON_LIMIT) return problem(413, "Request body too large");

  const parsed = LoginIn.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return problem(422, "Email and password are required");

  let upstream: Response;
  try {
    upstream = await fetch(new URL("/api/v1/auth/login", apiBase()), {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json" },
      body: JSON.stringify(parsed.data),
      cache: "no-store",
    });
  } catch {
    return problem(502, "The PortPilot API is not reachable");
  }
  if (!upstream.ok) {
    // One message for every 401 (the API does the same); 429 keeps its Retry-After.
    const retry = upstream.headers.get("retry-after");
    return problem(upstream.status, "Sign-in failed", retry ? { "retry-after": retry } : undefined);
  }

  const token = TokenOut.safeParse(await upstream.json().catch(() => null));
  if (!token.success) return problem(502, "Unexpected answer from the API");
  const seconds = (Date.parse(token.data.expires_at) - Date.now()) / 1000;
  if (!Number.isFinite(seconds) || seconds <= 0) return problem(502, "Unexpected answer from the API");

  const jar = await cookies();
  jar.set(SESSION_COOKIE, token.data.token, cookieOptions(true, seconds));
  jar.set(CSRF_COOKIE, newCsrfToken(), cookieOptions(false, seconds));
  return Response.json({ me: token.data.me }, { headers: { "cache-control": "no-store" } });
}
