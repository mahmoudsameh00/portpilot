// GET /healthz (Staging readiness plan P2, ADR-071): the proxy's, the deploy smoke test's and the uptime monitor's
// probe. 200 when this server answers and the API reports "ready"; 503 otherwise. The body names no component, no
// address and no error text (the API's /health/ready, behind a token, has the detail).
import { apiBase } from "@/lib/bff/core";

export const dynamic = "force-dynamic";

type ApiState = "ready" | "degraded" | "unreachable";

export async function GET(): Promise<Response> {
  let api: ApiState = "unreachable";
  try {
    const upstream = await fetch(new URL("/api/v1/health/status", apiBase()), {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    const body = (await upstream.json().catch(() => null)) as { status?: unknown } | null;
    api = body?.status === "ready" && upstream.ok ? "ready" : "degraded";
  } catch {
    api = "unreachable";
  }
  return Response.json(
    { status: api === "ready" ? "ok" : "unavailable", api },
    { status: api === "ready" ? 200 : 503, headers: { "cache-control": "no-store" } },
  );
}
