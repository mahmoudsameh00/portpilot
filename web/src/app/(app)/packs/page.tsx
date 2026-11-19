// The weekly packs (plan §6.4): week, attempt, waiting or ended. Finance + the CEO (the API decides; 403 → 404 here).
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PackList } from "@/components/packs/PackList";
import { AppTopBar } from "@/components/shell/AppTopBar";
import { getSession } from "@/lib/session";

export const metadata: Metadata = { title: "Reports — PortPilot" };

export default async function PacksPage() {
  const session = await getSession();
  if (session.kind !== "signed-in") return null;
  if (!session.me.products.packs_read) notFound();
  return (
    <>
      <AppTopBar me={session.me} active="/packs" />
      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <PackList canDecide={session.me.products.packs_decide} />
      </main>
    </>
  );
}
