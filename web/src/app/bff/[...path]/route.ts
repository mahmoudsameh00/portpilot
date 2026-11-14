// The BFF proxy (Frontend plan §3–§5): browser → /bff/<api path> → the API with the session's bearer token.
// Only (method, path) pairs from the OpenAPI schema pass; SSE and file downloads stream through unbuffered.
import { cookies } from "next/headers";
import {
  CSRF_COOKIE,
  CSRF_HEADER,
  FORWARD_REQUEST_HEADERS,
  FORWARD_RESPONSE_HEADERS,
  JSON_LIMIT,
  SESSION_COOKIE,
  UPLOAD_LIMIT,
  apiBase,
  csrfTokenMatches,
  matchRoute,
  problem,
  sameOrigin,
} from "@/lib/bff/core";

export const dynamic = "force-dynamic";

const PUBLIC_TEMPLATES = new Set(["/health/live"]); // /health/ready needs a session (ADR-064)

type Ctx = { params: Promise<{ path: string[] }> };

async function proxy(req: Request, ctx: Ctx): Promise<Response> {
  const { path } = await ctx.params;
  const method = req.method.toUpperCase();
  const template = matchRoute(method, path);
  if (template === null) return problem(404, "Not found");

  const jar = await cookies();
  if (method !== "GET" && method !== "HEAD") {
    // CSRF layers 2 + 3 (layer 1 = SameSite=Strict on both cookies).
    if (!sameOrigin(req) || !csrfTokenMatches(jar.get(CSRF_COOKIE)?.value, req.headers.get(CSRF_HEADER))) {
      return problem(403, "Request refused");
    }
  }

  const token = jar.get(SESSION_COOKIE)?.value;
  if (!token && !PUBLIC_TEMPLATES.has(template)) return problem(401, "Sign in required");

  const headers = new Headers();
  for (const name of FORWARD_REQUEST_HEADERS) {
    const value = req.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  if (token) headers.set("authorization", `Bearer ${token}`);

  let body: BodyInit | undefined;
  if (method !== "GET" && method !== "DELETE") {
    const isUpload = (req.headers.get("content-type") ?? "").startsWith("multipart/form-data");
    const limit = isUpload ? UPLOAD_LIMIT : JSON_LIMIT;
    const length = Number(req.headers.get("content-length") ?? "NaN");
    if (!Number.isFinite(length)) return problem(411, "Length required");
    if (length > limit) return problem(413, "Request body too large");
    const bytes = await req.arrayBuffer();
    if (bytes.byteLength > limit) return problem(413, "Request body too large");
    body = bytes;
  }

  const target = new URL(`/api/v1/${path.map(encodeURIComponent).join("/")}`, apiBase());
  target.search = new URL(req.url).search;

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method,
      headers,
      body,
      redirect: "manual",
      cache: "no-store",
      signal: req.signal, // the browser left → stop the upstream request (SSE included)
    });
  } catch {
    return problem(502, "The PortPilot API is not reachable");
  }

  const out = new Headers({ "cache-control": "no-store" });
  for (const name of FORWARD_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value !== null) out.set(name, value);
  }
  if ((out.get("content-type") ?? "").startsWith("text/event-stream")) out.set("x-accel-buffering", "no");

  if (upstream.status === 401) {
    jar.delete(SESSION_COOKIE);
    jar.delete(CSRF_COOKIE);
  }
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export const GET = proxy;
export const POST = proxy;
export const DELETE = proxy;
