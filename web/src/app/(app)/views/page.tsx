// Charts (plan §6.5): the reader's own view of the finance data; it never changes the published pack.
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { AppTopBar } from "@/components/shell/AppTopBar";
import { ViewsWorkspace } from "@/components/views/ViewsWorkspace";
import { getSession } from "@/lib/session";

export const metadata: Metadata = { title: "Charts — PortPilot" };

export default async function ViewsPage() {
  const session = await getSession();
  if (session.kind !== "signed-in") return null;
  if (!session.me.tools.includes("finance_kpi")) notFound();
  return (
    <>
      <AppTopBar me={session.me} active="/views" />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <h1 className="mb-6 text-2xl font-semibold">Charts</h1>
        <ViewsWorkspace />
      </main>
    </>
  );
}
