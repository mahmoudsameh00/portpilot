"use client";
// The Ask page (plan §6.3): conversations on the start side, the thread in the middle, the conversation's documents
// on the end side (uploads = untrusted, labelled as such by the API; promotion = a request a person reviews).
// Documents are attached from the composer's "+", from the first message on (D-FE-11).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp, FileText, Loader2, MessageSquarePlus, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useCallback, useState } from "react";
import {
  listConversationsApiV1ConversationsGet as listConversations,
  listUploadsApiV1ConversationsConversationIdUploadsGet as listUploads,
  promoteApiV1ConversationsConversationIdUploadsDocumentIdPromotionPost as promote,
} from "@/api/generated/client";
import { Button } from "@/components/ui/button";
import type { Me } from "@/lib/api-types";
import { BffError } from "@/lib/bff/client";
import { cn } from "@/lib/utils";
import { AskThread, type Attach } from "./AskThread";
import { useAskThread } from "./useAskThread";
import { UPLOAD_HINT, useAttachments } from "./useAttachments";

function startersFor(me: Me): string[] {
  const out: string[] = [];
  if (me.tools.includes("finance_kpi")) {
    out.push(
      "How much did PortPilot bill in week 23 of 2025?",
      "Which customers are most overdue this week?",
    );
  }
  if (me.products.voyage_watch || me.tools.includes("voyage_status")) {
    out.push("Which vessels are late against their schedule?");
  }
  out.push("فوترنا كام في أسبوع 23 من 2025؟");
  return out.slice(0, 4);
}

function Conversations({ current, onNew }: { current: string | null; onNew?: () => void }) {
  const { data, isPending } = useQuery({ queryKey: ["conversations"], queryFn: () => listConversations() });
  const items = [...(data ?? [])].sort((a, b) =>
    (b.last_turn_at ?? b.created_at).localeCompare(a.last_turn_at ?? a.created_at),
  );
  return (
    <nav aria-label="Conversations" className="flex flex-col gap-2">
      <Button asChild variant="outline" className="justify-start">
        <Link
          href="/ask"
          onClick={
            onNew
              ? (e) => {
                  e.preventDefault();
                  onNew();
                }
              : undefined
          }
        >
          <MessageSquarePlus aria-hidden /> New conversation
        </Link>
      </Button>
      <p className="mt-3 px-1 text-xs text-muted-foreground">Recent</p>
      {isPending ? (
        <Loader2 className="mx-auto size-4 animate-spin text-muted-foreground" aria-hidden />
      ) : null}
      <ul className="flex flex-col gap-1">
        {items.slice(0, 30).map((c) => (
          <li key={c.conversation_id}>
            <Link
              href={`/ask/${c.conversation_id}`}
              aria-current={c.conversation_id === current ? "page" : undefined}
              className={cn(
                "block rounded-md px-3 py-2 text-sm transition-colors",
                c.conversation_id === current
                  ? "bg-accent font-medium"
                  : "text-muted-foreground hover:bg-accent",
              )}
            >
              {new Intl.DateTimeFormat("en-GB", {
                dateStyle: "medium",
                timeStyle: "short",
                timeZone: "Africa/Cairo",
              }).format(new Date(c.last_turn_at ?? c.created_at))}
              {c.closed_at ? <span className="ms-2 text-xs">(closed)</span> : null}
            </Link>
          </li>
        ))}
        {!isPending && items.length === 0 ? (
          <li className="px-3 text-xs text-muted-foreground">No conversation yet.</li>
        ) : null}
      </ul>
    </nav>
  );
}

// The conversation's documents (D-FE-11): the list, what the screening removed, the promotion request. Attaching
// is the composer's "+" (one way in); this panel only reads the API's list.
function Documents({ conversationId, me }: { conversationId: string | null; me: Me }) {
  const docs = useQuery({
    queryKey: ["uploads", conversationId],
    queryFn: () => listUploads(conversationId as string),
    enabled: conversationId !== null,
  });
  const ask = useMutation({
    mutationFn: (documentId: string) => promote(conversationId as string, documentId, { note: "" }),
  });
  const canPromote = me.role === "manager" || me.role === "ceo";
  const items = docs.data ?? [];

  return (
    <section aria-label="Documents in this conversation" className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold">Documents</h2>
      <p className="text-xs text-muted-foreground">
        Attach with <span className="font-semibold">+</span> beside your question. {UPLOAD_HINT}
      </p>
      {items.length === 0 ? (
        <p className="text-xs text-muted-foreground">No document in this conversation yet.</p>
      ) : null}
      <ul className="flex flex-col gap-2">
        {items.map((d) => (
          <li key={d.document_id} className="rounded-lg border bg-card p-3 text-xs">
            <p className="flex items-center gap-1.5 font-medium">
              <FileText className="size-3.5 shrink-0 text-primary" aria-hidden />
              <span dir="auto" className="truncate">
                {d.title || d.filename}
              </span>
            </p>
            <p className="mt-1 font-mono text-muted-foreground">
              {d.document_code} · {d.chunks} chunks
            </p>
            {d.removed ? (
              <p className="mt-1 flex items-start gap-1 text-waiting-ink">
                <ShieldAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden /> {d.removed} section(s)
                removed by the screening.
              </p>
            ) : null}
            {canPromote ? (
              <Button
                variant="ghost"
                size="sm"
                className="mt-1 h-7 px-2 text-xs"
                disabled={ask.isPending}
                onClick={() => ask.mutate(d.document_id)}
              >
                <FileUp aria-hidden /> Ask to add to the library
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
      {ask.isSuccess ? <p className="text-xs text-approved-ink">Request sent for review.</p> : null}
      {ask.isError ? (
        <p role="alert" className="text-xs text-alert-ink">
          {ask.error instanceof BffError ? ask.error.title : "The request failed."}
        </p>
      ) : null}
    </section>
  );
}

// On /ask the first question moves the address to /ask/<id> in place (history.replaceState), so the router still has
// /ask mounted and a link to /ask would land on the same page with the old conversation in its state. There, "New
// conversation" puts the address back and mounts the workspace afresh (a new key); on /ask/<id> the link navigates.
export function AskWorkspace({ me, conversationId }: { me: Me; conversationId: string | null }) {
  const [fresh, setFresh] = useState(0);
  const onNew = useCallback(() => {
    window.history.replaceState(null, "", "/ask");
    setFresh((n) => n + 1);
  }, []);
  return (
    <Workspace
      key={fresh}
      me={me}
      conversationId={conversationId}
      onNew={conversationId === null ? onNew : undefined}
    />
  );
}

function Workspace({
  me,
  conversationId,
  onNew,
}: {
  me: Me;
  conversationId: string | null;
  onNew?: () => void;
}) {
  const qc = useQueryClient();
  const [current, setCurrent] = useState<string | null>(conversationId);
  const onCreated = useCallback(
    (id: string) => {
      setCurrent(id);
      window.history.replaceState(null, "", `/ask/${id}`);
      void qc.invalidateQueries({ queryKey: ["conversations"] });
    },
    [qc],
  );
  const { turns, loading, loadError, ask, ensureConversation, running } = useAskThread(
    conversationId,
    onCreated,
  );
  const attachments = useAttachments(me.products.uploads ? current : null, ensureConversation);
  const { takeSent } = attachments;
  // the documents accepted so far go with this question; their chips leave the composer
  const send = useCallback((question: string) => ask(question, takeSent()), [ask, takeSent]);
  const attach: Attach | undefined = me.products.uploads
    ? { items: attachments.items, onPick: attachments.add, onRemove: (id) => void attachments.remove(id) }
    : undefined;

  return (
    <main className="mx-auto grid h-[calc(100dvh-4rem)] max-w-7xl grid-cols-1 gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[15rem_minmax(0,1fr)_16rem]">
      <aside className="hidden overflow-y-auto lg:block">
        <Conversations current={current} onNew={onNew} />
      </aside>
      <section aria-label="Conversation" className="flex min-h-0 min-w-0 flex-col">
        {loadError ? (
          <p role="alert" className="mb-3 text-sm text-alert-ink">
            {loadError}
          </p>
        ) : null}
        {loading ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Loading the conversation…
          </p>
        ) : (
          <AskThread
            turns={turns}
            running={running}
            onAsk={send}
            starters={startersFor(me)}
            disabled={attachments.uploading}
            attach={attach}
          />
        )}
      </section>
      <aside className="hidden overflow-y-auto lg:block">
        {me.products.uploads ? <Documents conversationId={current} me={me} /> : null}
      </aside>
    </main>
  );
}
