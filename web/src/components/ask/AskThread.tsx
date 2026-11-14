"use client";
// The conversation as an assistant-ui thread (ADR-060, owner 2026-11-07: assistant-ui on a custom ExternalStoreRuntime).
// Our turns are the store; each assistant message carries its turn in `metadata.custom`, rendered by AnswerCard
// (receipts, trace, refusals). The API answers whole (no token streaming), so the run's progress is the trace.
import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAuiState,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from "@assistant-ui/react";
import { ArrowUp, FileText, Loader2, Paperclip, Plus, ShieldAlert, Sparkles, X } from "lucide-react";
import { useRef } from "react";
import { cn } from "@/lib/utils";
import { AnswerCard } from "./AnswerCard";
import type { Turn } from "./useAskThread";
import { UPLOAD_ACCEPT, UPLOAD_HINT, type Attachment } from "./useAttachments";

/** The composer's "+" (D-FE-11): absent when the asker has no uploads product. */
export type Attach = {
  items: Attachment[];
  onPick: (files: File[]) => void;
  onRemove: (id: string) => void;
};

type Msg = { id: string; role: "user" | "assistant"; text: string; turn: Turn };

const toMessages = (turns: Turn[]): Msg[] =>
  turns.flatMap((t) => [
    { id: `${t.id}:q`, role: "user" as const, text: t.question, turn: t },
    {
      id: `${t.id}:a`,
      role: "assistant" as const,
      text: typeof t.answer?.answer === "string" ? t.answer.answer : "",
      turn: t,
    },
  ]);

const convertMessage = (m: Msg): ThreadMessageLike => ({
  id: m.id,
  role: m.role,
  content: [{ type: "text", text: m.text }],
  metadata: { custom: { turn: m.turn } },
});

function UserMessage() {
  const turn = useAuiState((s) => s.message.metadata.custom?.["turn"] as Turn | undefined);
  const attached = turn?.attachments ?? [];
  return (
    <MessagePrimitive.Root className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl rounded-ee-sm bg-navy px-5 py-3.5 text-on-navy">
        {attached.length ? (
          <ul aria-label="Documents attached with this question" className="mb-2 flex flex-wrap gap-1.5">
            {attached.map((name, i) => (
              <li
                key={`${i}:${name}`}
                className="flex max-w-full items-center gap-1 rounded-md bg-white/12 px-2 py-1 text-xs"
              >
                <Paperclip className="size-3 shrink-0" aria-hidden />
                <bdi className="truncate">{name}</bdi>
              </li>
            ))}
          </ul>
        ) : null}
        <p dir="auto" className="text-[0.95rem] whitespace-pre-line">
          {turn?.question ?? ""}
        </p>
      </div>
    </MessagePrimitive.Root>
  );
}

function AttachmentChips({ attach }: { attach: Attach }) {
  return (
    <div className="flex flex-col gap-1.5 px-1.5 pt-1">
      <ul aria-label="Attached documents" aria-live="polite" className="flex flex-wrap gap-1.5">
        {attach.items.map((a) => (
          <li
            key={a.id}
            data-state={a.state}
            className={cn(
              "flex max-w-full items-start gap-2 rounded-lg border px-2.5 py-1.5 text-xs",
              a.state === "accepted" && "bg-approved-wash/50",
              a.state === "refused" && "bg-alert-wash/60",
            )}
          >
            {a.state === "uploading" ? (
              <Loader2 className="mt-0.5 size-3.5 shrink-0 animate-spin text-muted-foreground" aria-hidden />
            ) : a.state === "accepted" ? (
              <FileText className="mt-0.5 size-3.5 shrink-0 text-primary" aria-hidden />
            ) : (
              <ShieldAlert className="mt-0.5 size-3.5 shrink-0 text-alert-ink" aria-hidden />
            )}
            <span className="flex min-w-0 flex-col">
              <bdi className="truncate font-medium">{a.name}</bdi>
              <span className={a.state === "refused" ? "text-alert-ink" : "text-muted-foreground"}>
                {a.state === "uploading"
                  ? "Checking the document…"
                  : a.state === "accepted"
                    ? a.removed
                      ? `Accepted — ${a.removed} section(s) removed by the screening`
                      : "Accepted"
                    : `Not accepted — ${a.message ?? "the document was refused."}`}
              </span>
            </span>
            {a.state === "uploading" ? null : (
              <button
                type="button"
                aria-label={`Remove ${a.name}`}
                onClick={() => attach.onRemove(a.id)}
                className="-me-1 grid size-6 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <X className="size-3.5" aria-hidden />
              </button>
            )}
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted-foreground">{UPLOAD_HINT}</p>
    </div>
  );
}

function AssistantMessage() {
  const turn = useAuiState((s) => s.message.metadata.custom?.["turn"] as Turn | undefined);
  return <MessagePrimitive.Root>{turn ? <AnswerCard turn={turn} /> : null}</MessagePrimitive.Root>;
}

export function AskThread({
  turns,
  running,
  onAsk,
  starters,
  disabled,
  attach,
}: {
  turns: Turn[];
  running: boolean;
  onAsk: (question: string) => Promise<void>;
  starters: string[];
  disabled?: boolean;
  attach?: Attach;
}) {
  const picker = useRef<HTMLInputElement>(null);
  const runtime = useExternalStoreRuntime<Msg>({
    messages: toMessages(turns),
    convertMessage,
    isSendDisabled: running || disabled,
    onNew: async (message: AppendMessage) => {
      const part = message.content[0];
      if (part?.type !== "text" || !part.text.trim()) return;
      await onAsk(part.text.trim());
    },
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col">
        <ThreadPrimitive.Viewport className="flex min-h-0 flex-1 flex-col gap-8 overflow-y-auto px-1 pb-4">
          {turns.length === 0 ? (
            <div className="mx-auto mt-10 flex max-w-xl flex-col items-center text-center">
              <Sparkles className="size-8 text-primary" aria-hidden />
              <h2 className="mt-3 text-2xl font-semibold">Ask about any number</h2>
              <p className="mt-2 text-muted-foreground">
                Billing, receivables, voyages or routes — in English or Arabic. Every number in the answer
                comes with its receipt.
              </p>
              <ul className="mt-6 flex flex-col gap-2 self-stretch">
                {starters.map((q) => (
                  <li key={q}>
                    <button
                      type="button"
                      dir="auto"
                      disabled={running || disabled}
                      onClick={() => void onAsk(q)}
                      className="w-full rounded-lg border bg-card px-4 py-3 text-start text-sm transition-colors hover:border-primary disabled:opacity-60"
                    >
                      {q}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <ThreadPrimitive.Messages components={{ UserMessage, AssistantMessage }} />
        </ThreadPrimitive.Viewport>

        <ComposerPrimitive.Root className="flex flex-col gap-1 rounded-xl border bg-card p-1.5 shadow-float">
          {attach && attach.items.length ? <AttachmentChips attach={attach} /> : null}
          {/* "+" first, Send last: the interface is English (D-FE-6), so "+" stays at the left even when the
              question is Arabic — only the text inside the box turns (owner 2026-11-14). */}
          <div className="flex items-end gap-2">
            {attach ? (
              <>
                <input
                  ref={picker}
                  type="file"
                  multiple
                  hidden
                  tabIndex={-1}
                  accept={UPLOAD_ACCEPT}
                  onChange={(e) => {
                    const files = [...(e.target.files ?? [])];
                    e.target.value = "";
                    if (files.length) attach.onPick(files);
                  }}
                />
                <button
                  type="button"
                  aria-label="Attach documents"
                  title={UPLOAD_HINT}
                  disabled={running}
                  onClick={() => picker.current?.click()}
                  className="grid size-11 shrink-0 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-40"
                >
                  <Plus className="size-5" aria-hidden />
                </button>
              </>
            ) : null}
            <ComposerPrimitive.Input
              dir="auto"
              rows={1}
              maxLength={2000}
              aria-label="Ask PortPilot"
              placeholder={
                attach
                  ? "Ask a question, or attach a document with +"
                  : "Ask a question, in English or Arabic"
              }
              className="max-h-40 min-h-11 min-w-0 flex-1 resize-none bg-transparent px-3 py-3 text-sm outline-none"
            />
            <ComposerPrimitive.Send
              aria-label="Ask"
              className="grid size-11 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground transition-opacity disabled:opacity-40"
            >
              <ArrowUp className="size-5" aria-hidden />
            </ComposerPrimitive.Send>
          </div>
        </ComposerPrimitive.Root>
      </ThreadPrimitive.Root>
    </AssistantRuntimeProvider>
  );
}
