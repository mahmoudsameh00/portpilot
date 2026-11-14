"use client";
// The Ask page (plan §6.3): conversations on the start side, the thread in the middle, the conversation's documents
// on the end side (uploads = untrusted, labelled as such by the API; promotion = a request a person reviews).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp, FileText, Loader2, MessageSquarePlus, ShieldAlert, Upload } from "lucide-react";
import Link from "next/link";
import { useCallback, useRef, useState } from "react";
import {
  listConversationsApiV1ConversationsGet as listConversations,
  listUploadsApiV1ConversationsConversationIdUploadsGet as listUploads,
  promoteApiV1ConversationsConversationIdUploadsDocumentIdPromotionPost as promote,
  uploadApiV1ConversationsConversationIdUploadsPost as uploadFile,
  type UploadOut,
} from "@/api/generated/client";
import { Button } from "@/components/ui/button";
import type { Me } from "@/lib/api-types";
import { BffError } from "@/lib/bff/client";
import { cn } from "@/lib/utils";
import { AskThread } from "./AskThread";
import { useAskThread } from "./useAskThread";

const MAX_UPLOAD = 5 * 1024 * 1024;

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

function Conversations({ current }: { current: string | null }) {
  const { data, isPending } = useQuery({ queryKey: ["conversations"], queryFn: () => listConversations() });
  const items = [...(data ?? [])].sort((a, b) =>
    (b.last_turn_at ?? b.created_at).localeCompare(a.last_turn_at ?? a.created_at),
  );
  return (
    <nav aria-label="Conversations" className="flex flex-col gap-2">
      <Button asChild variant="outline" className="justify-start">
        <Link href="/ask">
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

function Documents({ conversationId, me }: { conversationId: string; me: Me }) {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [verdict, setVerdict] = useState<UploadOut | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const docs = useQuery({
    queryKey: ["uploads", conversationId],
    queryFn: () => listUploads(conversationId),
  });
  const send = useMutation({
    mutationFn: (file: File) => uploadFile(conversationId, { file }),
    onSuccess: (out) => {
      setVerdict(out);
      setProblem(null);
      void qc.invalidateQueries({ queryKey: ["uploads", conversationId] });
    },
    onError: (error) => setProblem(error instanceof BffError ? error.title : "The upload failed."),
  });
  const ask = useMutation({
    mutationFn: (documentId: string) => promote(conversationId, documentId, { note: "" }),
  });
  const canPromote = me.role === "manager" || me.role === "ceo";

  return (
    <section aria-label="Documents in this conversation" className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold">Documents</h2>
      <p className="text-xs text-muted-foreground">
        PDF or Word, up to 5 MB. Uploaded text is treated as untrusted and labelled so in answers.
      </p>
      <input
        ref={input}
        type="file"
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="sr-only"
        aria-label="Upload a document"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (!file) return;
          if (file.size > MAX_UPLOAD) {
            setProblem("This file is larger than 5 MB.");
            return;
          }
          send.mutate(file);
        }}
      />
      <Button variant="outline" size="sm" disabled={send.isPending} onClick={() => input.current?.click()}>
        {send.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Upload aria-hidden />} Upload
      </Button>
      {problem ? (
        <p role="alert" className="text-xs text-alert-ink">
          {problem}
        </p>
      ) : null}
      {verdict ? (
        <div
          className={cn(
            "rounded-lg border p-3 text-xs",
            verdict.accepted ? "bg-approved-wash/50" : "bg-alert-wash/60",
          )}
        >
          <p className="font-semibold">{verdict.accepted ? "Accepted" : "Not accepted"}</p>
          <p className="mt-1 text-muted-foreground">{verdict.message}</p>
          {verdict.removed.length ? (
            <p className="mt-1 flex items-start gap-1 text-waiting-ink">
              <ShieldAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden /> {verdict.removed.length}{" "}
              section(s) removed by the screening.
            </p>
          ) : null}
        </div>
      ) : null}
      <ul className="flex flex-col gap-2">
        {(docs.data ?? []).map((d) => (
          <li key={d.document_id} className="rounded-lg border bg-card p-3 text-xs">
            <p className="flex items-center gap-1.5 font-medium">
              <FileText className="size-3.5 text-primary" aria-hidden />
              <span dir="auto" className="truncate">
                {d.title || d.filename}
              </span>
            </p>
            <p className="mt-1 font-mono text-muted-foreground">
              {d.document_code} · {d.chunks} chunks
            </p>
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

export function AskWorkspace({ me, conversationId }: { me: Me; conversationId: string | null }) {
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
  const { turns, loading, loadError, ask, running } = useAskThread(conversationId, onCreated);

  return (
    <main className="mx-auto grid h-[calc(100dvh-4rem)] max-w-7xl grid-cols-1 gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[15rem_minmax(0,1fr)_16rem]">
      <aside className="hidden overflow-y-auto lg:block">
        <Conversations current={current} />
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
          <AskThread turns={turns} running={running} onAsk={ask} starters={startersFor(me)} />
        )}
      </section>
      <aside className="hidden overflow-y-auto lg:block">
        {me.products.uploads && current ? (
          <Documents conversationId={current} me={me} />
        ) : (
          <p className="text-xs text-muted-foreground">
            {me.products.uploads ? "Ask a first question to attach documents to this conversation." : ""}
          </p>
        )}
      </aside>
    </main>
  );
}
