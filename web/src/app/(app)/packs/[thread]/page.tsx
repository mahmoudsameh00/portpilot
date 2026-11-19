// One pack, reviewed slide by slide (plan §6.4, D-FE-9).
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PackReview } from "@/components/packs/PackReview";
import { AppTopBar } from "@/components/shell/AppTopBar";
import { getSession } from "@/lib/session";

export const metadata: Metadata = { title: "Pack review — PortPilot" };

const THREAD = /^[A-Za-z0-9._:~-]{1,200}$/;

export default async function PackPage({ params }: PageProps<"/packs/[thread]">) {
  const thread = decodeURIComponent((await params).thread);
  if (!THREAD.test(thread)) notFound();
  const session = await getSession();
  if (session.kind !== "signed-in") return null;
  if (!session.me.products.packs_read) notFound();
  return (
    <>
      <AppTopBar me={session.me} active="/packs" />
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <PackReview thread={thread} />
      </main>
    </>
  );
}
