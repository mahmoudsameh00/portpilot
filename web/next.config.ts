import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

// Security headers that do not need a per-request value; the CSP (with its nonce) is set in src/proxy.ts.
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
];

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  // Owner 2026-11-15: the tabs are named Reports and Dashboards; their pages keep /packs and /finance
  async redirects() {
    return [
      { source: "/reports", destination: "/packs", permanent: false },
      { source: "/reports/:path*", destination: "/packs/:path*", permanent: false },
      { source: "/dashboards", destination: "/finance", permanent: false },
    ];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");
export default withNextIntl(nextConfig);
