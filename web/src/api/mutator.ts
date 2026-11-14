// Orval's fetch goes through the BFF (plan §3): /api/v1/<path> → /bff/<path>, the CSRF header, the sign-in redirect.
// Errors are thrown as BffError (status, title, Retry-After); a success returns the body.
import { bffFetch } from "@/lib/bff/client";

export async function apiFetch<T>(url: string, init: RequestInit = {}): Promise<T> {
  return bffFetch<T>(url.replace(/^\/api\/v1/, ""), init);
}
