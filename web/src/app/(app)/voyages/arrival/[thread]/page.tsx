// One arrival advice (Arrival advice web plan, ADR-070): GET /arrival-advice/{thread}; the API decides who reads it.
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { AppTopBar } from "@/components/shell/AppTopBar";
import { ArrivalDetail } from "@/components/voyages/ArrivalDetail";
import { getSession } from "@/lib/session";

export const metadata: Metadata = { title: "Arrival advice — PortPilot" };

const THREAD = /^arrival_advice:\d{1,9}:\d{4}-\d{2}-\d{2}:\d{1,9}:\d{1,4}$/;

export default async function ArrivalAdvicePage({ params }: PageProps<"/voyages/arrival/[thread]">) {
  const thread = decodeURIComponent((await params).thread);
  if (!THREAD.test(thread)) notFound();
  const session = await getSession();
  if (session.kind !== "signed-in") return null;
  if (!session.me.products.arrival_advice) notFound();
  return (
    <>
      <AppTopBar me={session.me} active="/voyages" />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <Suspense>
          <ArrivalDetail key={thread} thread={thread} />
        </Suspense>
      </main>
    </>
  );
}
