// Who is signed in, read on the server (plan §4.1 (4)): the session cookie's token → GET /me at the API. The browser
// never sees the token; pages get `me` from here.
import "server-only";
import { cookies } from "next/headers";
import { cache } from "react";
import type { Me } from "./api-types";
import { SESSION_COOKIE, apiBase } from "./bff/core";

export type Session = { kind: "signed-in"; me: Me } | { kind: "signed-out" } | { kind: "api-down" };

/** One GET /me per request, however many layouts and pages ask (React `cache`). */
export const getSession = cache(async (): Promise<Session> => {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return { kind: "signed-out" };
  try {
    const res = await fetch(new URL("/api/v1/me", apiBase()), {
      headers: { authorization: `Bearer ${token}`, accept: "application/json" },
      cache: "no-store",
    });
    if (res.status === 401) return { kind: "signed-out" };
    if (!res.ok) return { kind: "api-down" };
    return { kind: "signed-in", me: (await res.json()) as Me };
  } catch {
    return { kind: "api-down" };
  }
});

/** A same-origin path to return to after sign-in; anything else (absolute, protocol-relative, odd) → "/". */
export function safeNext(raw: string | null | undefined): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return "/";
  if (/[\u0000-\u001f]/.test(raw) || raw.startsWith("/login") || raw.startsWith("/bff")) return "/";
  return raw;
}
