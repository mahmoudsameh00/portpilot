// Ask (plan §6.3): a new conversation. The first question creates it; the address then becomes /ask/<id>.
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { AskWorkspace } from "@/components/ask/AskWorkspace";
import { AppTopBar } from "@/components/shell/AppTopBar";
import { getSession } from "@/lib/session";

export const metadata: Metadata = { title: "Ask — PortPilot" };

export default async function AskPage() {
  const session = await getSession();
  if (session.kind !== "signed-in") return null;
  if (!session.me.products.ask) notFound();
  return (
    <>
      <AppTopBar me={session.me} active="/ask" />
      <AskWorkspace me={session.me} conversationId={null} />
    </>
  );
}
