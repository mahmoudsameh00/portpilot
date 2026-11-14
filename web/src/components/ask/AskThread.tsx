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
import { ArrowUp, Sparkles } from "lucide-react";
import { AnswerCard } from "./AnswerCard";
import type { Turn } from "./useAskThread";

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
  const text = useAuiState((s) => (s.message.metadata.custom?.["turn"] as Turn | undefined)?.question ?? "");
  return (
    <MessagePrimitive.Root className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl rounded-ee-sm bg-navy px-5 py-3.5 text-on-navy">
        <p dir="auto" className="text-[0.95rem] whitespace-pre-line">
          {text}
        </p>
      </div>
    </MessagePrimitive.Root>
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
}: {
  turns: Turn[];
  running: boolean;
  onAsk: (question: string) => Promise<void>;
  starters: string[];
  disabled?: boolean;
}) {
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

        <ComposerPrimitive.Root className="flex items-end gap-2 rounded-xl border bg-card p-1.5 shadow-float">
          <ComposerPrimitive.Input
            dir="auto"
            rows={1}
            maxLength={2000}
            aria-label="Ask PortPilot"
            placeholder="Ask a question, in English or Arabic"
            className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-3 py-3 text-sm outline-none"
          />
          <ComposerPrimitive.Send
            aria-label="Ask"
            className="grid size-11 place-items-center rounded-lg bg-primary text-primary-foreground transition-opacity disabled:opacity-40"
          >
            <ArrowUp className="size-5" aria-hidden />
          </ComposerPrimitive.Send>
        </ComposerPrimitive.Root>
      </ThreadPrimitive.Root>
    </AssistantRuntimeProvider>
  );
}
