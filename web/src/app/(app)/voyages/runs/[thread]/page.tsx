// One voyage-watch run (plan §6.7): its alerts, brief and fleet counts (GET /voyage-watch/runs/{thread}).
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { AppTopBar } from "@/components/shell/AppTopBar";
import { VoyageWatch } from "@/components/voyages/VoyageWatch";
import { getSession } from "@/lib/session";

export const metadata: Metadata = { title: "Voyage watch run — PortPilot" };

const THREAD = /^voyage_watch:[0-9TZ]{14}:\d{1,4}$/;

export default async function WatchRunPage({ params }: PageProps<"/voyages/runs/[thread]">) {
  const thread = decodeURIComponent((await params).thread);
  if (!THREAD.test(thread)) notFound();
  const session = await getSession();
  if (session.kind !== "signed-in") return null;
  if (!session.me.products.voyage_watch) notFound();
  return (
    <>
      <AppTopBar me={session.me} active="/voyages" />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <Suspense>
          <VoyageWatch key={thread} thread={thread} />
        </Suspense>
      </main>
    </>
  );
}
