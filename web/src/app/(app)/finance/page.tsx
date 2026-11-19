// The finance dashboard (plan §6.9, D-FE-7): the Power BI pages in the web, same views, same numbers.
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { FinanceDashboard } from "@/components/finance/FinanceDashboard";
import { AppTopBar } from "@/components/shell/AppTopBar";
import { getSession } from "@/lib/session";

export const metadata: Metadata = { title: "Dashboards — PortPilot" };

export default async function FinancePage() {
  const session = await getSession();
  if (session.kind !== "signed-in") return null;
  if (!session.me.tools.includes("finance_kpi")) notFound();
  return (
    <>
      <AppTopBar me={session.me} active="/finance" />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <Suspense>
          <FinanceDashboard />
        </Suspense>
      </main>
    </>
  );
}
