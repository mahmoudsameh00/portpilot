// The voyage watch (plan §6.7): the latest run's alerts as a radar list, its brief and the runs. Read only.
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { AppTopBar } from "@/components/shell/AppTopBar";
import { VoyageWatch } from "@/components/voyages/VoyageWatch";
import { getSession } from "@/lib/session";

export const metadata: Metadata = { title: "Voyage watch — PortPilot" };

export default async function VoyagesPage() {
  const session = await getSession();
  if (session.kind !== "signed-in") return null;
  if (!session.me.products.voyage_watch) notFound();
  return (
    <>
      <AppTopBar me={session.me} active="/voyages" />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <Suspense>
          <VoyageWatch canAdvise={session.me.products.arrival_advice ?? false} />
        </Suspense>
      </main>
    </>
  );
}
