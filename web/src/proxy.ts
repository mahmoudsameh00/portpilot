// Request proxy (Next.js 16 "proxy", formerly middleware): a CSP with a fresh nonce on every page (plan §4.5).
// /bff/* and static files are not matched: the BFF sets its own headers.
import { NextResponse, type NextRequest } from "next/server";

function contentSecurityPolicy(nonce: string): string {
  const dev = process.env.NODE_ENV === "development";
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${dev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'", // accepted risk: Recharts / Radix inline style attributes (plan §4.5)
    "img-src 'self' data: blob:",
    "font-src 'self'",
    `connect-src 'self'${dev ? " ws:" : ""}`,
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const csp = contentSecurityPolicy(nonce);
  const headers = new Headers(request.headers);
  headers.set("x-nonce", nonce);
  headers.set("x-portpilot-path", request.nextUrl.pathname + request.nextUrl.search); // for the sign-in return path
  headers.set("content-security-policy", csp); // Next.js reads the nonce from here for its own scripts
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("content-security-policy", csp);
  return response;
}

export const config = {
  // Everything except the BFF, Next's own files and files with an extension (fonts, icons).
  matcher: ["/((?!bff|_next|.*\\..*).*)"],
};
