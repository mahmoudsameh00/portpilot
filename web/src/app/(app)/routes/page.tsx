// Route advice (plan §6.6): the form, the decision view and the earlier advice. Operations + the CEO (from /me).
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { RouteWorkspace } from "@/components/routes/RouteWorkspace";
import { AppTopBar } from "@/components/shell/AppTopBar";
import { getSession } from "@/lib/session";

export const metadata: Metadata = { title: "Route advice — PortPilot" };

const LOCODE = /^[A-Z]{2}[A-Z2-9]{3}$/;

export default async function RoutesPage({ searchParams }: PageProps<"/routes">) {
  const session = await getSession();
  if (session.kind !== "signed-in") return null;
  if (!session.me.products.route_advice) notFound();
  // "Compare routes" from an arrival advice: a vessel id and a LOCODE, both checked here (nothing else is read)
  const sp = await searchParams;
  const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : undefined);
  const vessel = one(sp.vessel);
  const destination = one(sp.destination)?.toUpperCase();
  const prefill = {
    ...(vessel && /^\d{1,9}$/.test(vessel) ? { vessel } : {}),
    ...(destination && LOCODE.test(destination) ? { destination } : {}),
  };
  return (
    <>
      <AppTopBar me={session.me} active="/routes" />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <RouteWorkspace prefill={prefill} />
      </main>
    </>
  );
}
