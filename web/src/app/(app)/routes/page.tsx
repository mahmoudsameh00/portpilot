// Route advice (plan §6.6): the form, the decision view and the earlier advice. Operations + the CEO (from /me).
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { RouteWorkspace } from "@/components/routes/RouteWorkspace";
import { AppTopBar } from "@/components/shell/AppTopBar";
import { getSession } from "@/lib/session";

export const metadata: Metadata = { title: "Route advice — PortPilot" };

export default async function RoutesPage() {
  const session = await getSession();
  if (session.kind !== "signed-in") return null;
  if (!session.me.products.route_advice) notFound();
  return (
    <>
      <AppTopBar me={session.me} active="/routes" />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <RouteWorkspace />
      </main>
    </>
  );
}
