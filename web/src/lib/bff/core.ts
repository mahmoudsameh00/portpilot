// The BFF's rules (Frontend plan §4): one fixed upstream, an allow-list from OpenAPI, CSRF in three layers,
// header allow-lists both ways, body limits. Server-only: never imported by a client component.
import "server-only";
import { ALLOWED_ROUTES } from "./allowlist.generated";
import { CSRF_COOKIE_NAME, CSRF_HEADER_NAME } from "./names";

export const SESSION_COOKIE = "ng_session"; // the API's opaque bearer token: httpOnly, never readable by JS
export const CSRF_COOKIE = CSRF_COOKIE_NAME; // double-submit value: readable, echoed in X-CSRF-Token
export const CSRF_HEADER = CSRF_HEADER_NAME;

/** The API base URL — fixed from the environment, never from the request (no open proxy, no SSRF). */
export function apiBase(): string {
  const raw = process.env.PORTPILOT_API_URL ?? process.env.NILEGATE_API_URL ?? "http://127.0.0.1:8000";
  const url = new URL(raw);
  if (url.protocol !== "http:" && url.protocol !== "https:")
    throw new Error("PORTPILOT_API_URL must be http(s)");
  return url.origin;
}

/** The app's own origin, used by the Origin check. */
export function appOrigin(): string {
  return new URL(
    process.env.PORTPILOT_WEB_ORIGIN ?? process.env.NILEGATE_WEB_ORIGIN ?? "http://localhost:3000",
  ).origin;
}

// A path parameter: ids, thread ids ("ask:…", "pack:…"), UN/LOCODEs. Never "." / ".." and no slash.
const SEGMENT = /^[A-Za-z0-9._:~-]{1,200}$/;

/** Returns the matched template, or null when (method, path) is not in the API's schema. */
export function matchRoute(method: string, segments: readonly string[]): string | null {
  for (const route of ALLOWED_ROUTES) {
    if (route.method !== method) continue;
    const parts = route.template.split("/").slice(1);
    if (parts.length !== segments.length) continue;
    const ok = parts.every((part, i) => {
      const seg = segments[i] ?? "";
      if (part.startsWith("{") && part.endsWith("}")) return SEGMENT.test(seg) && seg !== "." && seg !== "..";
      return part === seg;
    });
    if (ok) return route.template;
  }
  return null;
}

/** Layer 2 of CSRF: the request must come from this origin (Origin header, or Sec-Fetch-Site). */
export function sameOrigin(req: Request): boolean {
  const origin = req.headers.get("origin");
  if (origin !== null) return origin === appOrigin();
  return req.headers.get("sec-fetch-site") === "same-origin";
}

/** Layer 3 of CSRF: the double-submit header equals the cookie (constant-time compare). */
export function csrfTokenMatches(cookieValue: string | undefined, headerValue: string | null): boolean {
  if (!cookieValue || !headerValue || cookieValue.length !== headerValue.length) return false;
  let diff = 0;
  for (let i = 0; i < cookieValue.length; i++) diff |= cookieValue.charCodeAt(i) ^ headerValue.charCodeAt(i);
  return diff === 0;
}

export function newCsrfToken(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return Buffer.from(bytes).toString("base64url");
}

export const FORWARD_REQUEST_HEADERS = ["content-type", "accept", "last-event-id", "x-request-id"] as const;
export const FORWARD_RESPONSE_HEADERS = [
  "content-type",
  "content-disposition",
  "retry-after",
  "x-request-id",
  "cache-control",
] as const;

// The API's own limits (ADR-064): 16 KB JSON, 5 MB uploads.
export const JSON_LIMIT = 16 * 1024;
export const UPLOAD_LIMIT = 5 * 1024 * 1024;

export function problem(status: number, title: string, headers?: HeadersInit): Response {
  return Response.json({ title, status }, { status, headers: { "cache-control": "no-store", ...headers } });
}

/** Cookie options shared by both cookies; `Secure` works on http://localhost (a secure context). */
export function cookieOptions(httpOnly: boolean, maxAgeSeconds: number) {
  return {
    httpOnly,
    sameSite: "strict" as const,
    secure: true,
    path: "/",
    maxAge: Math.max(0, Math.floor(maxAgeSeconds)),
  };
}
