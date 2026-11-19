// The approval report (plan §6.4, ADR-054 G5): decisions and edits across packs, for those who may decide.
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PackReport } from "@/components/packs/PackList";
import { AppTopBar } from "@/components/shell/AppTopBar";
import { getSession } from "@/lib/session";

export const metadata: Metadata = { title: "Approval report — PortPilot" };

export default async function ReportPage() {
  const session = await getSession();
  if (session.kind !== "signed-in") return null;
  if (!session.me.products.packs_decide) notFound();
  return (
    <>
      <AppTopBar me={session.me} active="/packs" />
      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <PackReport />
      </main>
    </>
  );
}
