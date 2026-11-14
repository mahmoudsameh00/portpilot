// The product menu (plan §6.2), built from `/me` — a comfort only: the API refuses what the asker may not use.
import type { Me } from "@/lib/api-types";

export type NavItem = { href: string; label: string; phase: string | null; show: (me: Me) => boolean };

// `phase` = the plan phase that builds the page; null = built. Unbuilt pages show as "soon", never as a dead link.
export const NAV: NavItem[] = [
  { href: "/", label: "Today", phase: null, show: () => true },
  { href: "/ask", label: "Ask", phase: null, show: (me) => me.products.ask },
  { href: "/packs", label: "Weekly pack", phase: null, show: (me) => me.products.packs_read },
  { href: "/views", label: "Charts", phase: null, show: (me) => me.tools.includes("finance_kpi") },
  { href: "/finance", label: "Finance", phase: null, show: (me) => me.tools.includes("finance_kpi") },
  { href: "/voyages", label: "Voyages", phase: null, show: (me) => me.products.voyage_watch },
  { href: "/routes", label: "Routes", phase: null, show: (me) => me.products.route_advice },
];
