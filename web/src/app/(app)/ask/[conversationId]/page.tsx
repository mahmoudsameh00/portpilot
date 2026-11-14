// Ask (plan §6.3): one conversation and its history. Not yours or unknown → the API's 404, shown in the thread.
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { AskWorkspace } from "@/components/ask/AskWorkspace";
import { AppTopBar } from "@/components/shell/AppTopBar";
import { getSession } from "@/lib/session";

export const metadata: Metadata = { title: "Ask — PortPilot" };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default async function ConversationPage({ params }: PageProps<"/ask/[conversationId]">) {
  const { conversationId } = await params;
  if (!UUID.test(conversationId)) notFound();
  const session = await getSession();
  if (session.kind !== "signed-in") return null;
  if (!session.me.products.ask) notFound();
  return (
    <>
      <AppTopBar me={session.me} active="/ask" />
      <AskWorkspace me={session.me} conversationId={conversationId} />
    </>
  );
}
