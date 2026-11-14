"use client";
// The browser's only way to the API (plan §3): same-origin /bff/*, the double-submit CSRF header on unsafe methods,
// and a session that ended sends the user to sign in again (same-origin return path only).
import { CSRF_COOKIE_NAME, CSRF_HEADER_NAME } from "./names";

export class BffError extends Error {
  constructor(
    public status: number,
    public title: string,
    public retryAfter: number | null,
  ) {
    super(title);
  }
}

function csrfToken(): string {
  const hit = document.cookie.split("; ").find((c) => c.startsWith(`${CSRF_COOKIE_NAME}=`));
  return hit ? decodeURIComponent(hit.slice(CSRF_COOKIE_NAME.length + 1)) : "";
}

export async function bffFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  headers.set("accept", "application/json");
  if (method !== "GET" && method !== "HEAD") headers.set(CSRF_HEADER_NAME, csrfToken());
  const res = await fetch(`/bff${path}`, {
    ...init,
    method,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });
  if (res.status === 401) {
    const here = window.location.pathname + window.location.search;
    // A full load on purpose: the session is gone, so every cached query and client state must go with it.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign(`/login?next=${encodeURIComponent(here)}`);
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { title?: string };
    const retry = Number(res.headers.get("retry-after"));
    throw new BffError(res.status, body.title ?? res.statusText, Number.isFinite(retry) ? retry : null);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}
