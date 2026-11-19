// POST /bff/logout: revoke the token at the API (api.tokens), then clear both cookies whatever the API said.
import { cookies } from "next/headers";
import {
  CSRF_COOKIE,
  CSRF_HEADER,
  SESSION_COOKIE,
  apiBase,
  csrfTokenMatches,
  problem,
  sameOrigin,
} from "@/lib/bff/core";

export const dynamic = "force-dynamic";

export async function POST(req: Request): Promise<Response> {
  const jar = await cookies();
  if (!sameOrigin(req) || !csrfTokenMatches(jar.get(CSRF_COOKIE)?.value, req.headers.get(CSRF_HEADER))) {
    return problem(403, "Request refused");
  }
  const token = jar.get(SESSION_COOKIE)?.value;
  if (token) {
    await fetch(new URL("/api/v1/auth/logout", apiBase()), {
      method: "POST",
      headers: { authorization: `Bearer ${token}` },
      cache: "no-store",
    }).catch(() => undefined);
  }
  jar.delete(SESSION_COOKIE);
  jar.delete(CSRF_COOKIE);
  return new Response(null, { status: 204, headers: { "cache-control": "no-store" } });
}
