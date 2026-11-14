// One route advice (plan §6.6): GET /route-advice/{thread} — the asker's own (the CEO's: any); the API decides.
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { RouteWorkspace } from "@/components/routes/RouteWorkspace";
import { AppTopBar } from "@/components/shell/AppTopBar";
import { getSession } from "@/lib/session";

export const metadata: Metadata = { title: "Route advice — PortPilot" };

const THREAD = /^[A-Za-z0-9._:~-]{1,200}$/;

export default async function RouteAdvicePage({ params }: PageProps<"/routes/[thread]">) {
  const thread = decodeURIComponent((await params).thread);
  if (!THREAD.test(thread)) notFound();
  const session = await getSession();
  if (session.kind !== "signed-in") return null;
  if (!session.me.products.route_advice) notFound();
  return (
    <>
      <AppTopBar me={session.me} active="/routes" />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <RouteWorkspace key={thread} thread={thread} />
      </main>
    </>
  );
}
