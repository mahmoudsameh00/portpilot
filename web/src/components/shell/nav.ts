// The product menu (plan §6.2), built from `/me` — a comfort only: the API refuses what the asker may not use.
import type { Me } from "@/lib/api-types";

export type NavItem = { href: string; label: string; phase: string | null; show: (me: Me) => boolean };

// `phase` = the plan phase that builds the page; null = built. Unbuilt pages show as "soon", never as a dead link.
// Owner 2026-11-15 (web dashboards plan §2e): "Weekly pack" → Reports, "Finance" → Dashboards; the URLs stay
// /packs and /finance (/reports and /dashboards redirect to them).
// Home (`/`) has no entry: the PortPilot wordmark opens it (owner 2026-11-14, D-FE-11 — the "Today" tab removed).
export const NAV: NavItem[] = [
  { href: "/ask", label: "Ask", phase: null, show: (me) => me.products.ask },
  { href: "/packs", label: "Reports", phase: null, show: (me) => me.products.packs_read },
  { href: "/views", label: "Charts", phase: null, show: (me) => me.tools.includes("finance_kpi") },
  { href: "/finance", label: "Dashboards", phase: null, show: (me) => me.tools.includes("finance_kpi") },
  { href: "/voyages", label: "Voyages", phase: null, show: (me) => me.products.voyage_watch },
  { href: "/routes", label: "Routes", phase: null, show: (me) => me.products.route_advice },
];
