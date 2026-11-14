"use client";
// One conversation's turns (plan §6.3): the history from the API, a new question → a run → its events folded into
// the turn. The API decides everything (RBAC, refusals, numbers); this only keeps what it said, in order.
import { useCallback, useEffect, useRef, useState } from "react";
import {
  askQuestionApiV1ConversationsConversationIdQuestionsPost as askQuestion,
  getConversationApiV1ConversationsConversationIdGet as getConversation,
  getQuestionApiV1QuestionsThreadIdGet as getQuestion,
  openConversationApiV1ConversationsPost as openConversation,
  type AnswerData,
  type RunEventSchema,
} from "@/api/generated/client";
import { BffError } from "@/lib/bff/client";
import { RunObservationError, streamRun } from "@/lib/runs";

export type ToolMark = { name: string; state: "called" | "refused"; part?: string };

export type Turn = {
  id: string;
  question: string;
  state: "running" | "done" | "failed";
  queued?: number;
  understood?: { text: string; by: string };
  nodes: string[];
  tools: ToolMark[];
  answer?: AnswerData;
  error?: string;
};

const newTurn = (question: string): Turn => ({
  id: crypto.randomUUID(),
  question,
  state: "running",
  nodes: [],
  tools: [],
});

/** Folds one run event into its turn (pure: the tests call it directly). */
export function applyEvent(turn: Turn, event: RunEventSchema): Turn {
  switch (event.event) {
    case "queued":
      return { ...turn, queued: event.data.position };
    case "started":
      return { ...turn, queued: undefined };
    case "understood":
      return { ...turn, understood: { text: event.data.standalone_question, by: event.data.by } };
    case "node":
      return event.data.phase === "start" && !turn.nodes.includes(event.data.name)
        ? { ...turn, nodes: [...turn.nodes, event.data.name] }
        : turn;
    case "tool_called":
      return turn.tools.some((t) => t.name === event.data.name)
        ? turn
        : { ...turn, tools: [...turn.tools, { name: event.data.name, state: "called" }] };
    case "tool_refused":
      return {
        ...turn,
        tools: [...turn.tools, { name: event.data.name, state: "refused", part: event.data.part }],
      };
    case "answer":
      return { ...turn, answer: event.data };
    case "done":
      return { ...turn, state: "done" };
    case "failed":
      return { ...turn, state: "failed", error: event.data.detail };
    default:
      return turn;
  }
}

function problemText(error: unknown): string {
  if (error instanceof RunObservationError) return error.message;
  if (error instanceof BffError) {
    if (error.status === 409) return "This conversation is still answering. Wait for it, then ask again.";
    if (error.status === 429)
      return `Too many questions right now. Try again in ${Math.max(1, Math.ceil((error.retryAfter ?? 60) / 60))} minute(s).`;
    if (error.status === 404) return "This conversation is not available.";
    return error.title;
  }
  return "The question could not be sent. Try again.";
}

export function useAskThread(conversationId: string | null, onCreated: (id: string) => void) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(conversationId !== null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const idRef = useRef<string | null>(conversationId);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    idRef.current = conversationId;
    if (conversationId === null) {
      setTurns([]);
      setLoading(false);
      return;
    }
    let live = true;
    setLoading(true);
    (async () => {
      try {
        const detail = await getConversation(conversationId);
        const loaded = await Promise.all(
          detail.turns.map(async (t): Promise<Turn> => {
            const base: Turn = { ...newTurn(t.question), id: `h${t.turn_no}`, state: "done" };
            if (!t.thread_id) return { ...base, answer: { status: t.status ?? null } as AnswerData };
            try {
              return { ...base, answer: await getQuestion(t.thread_id) };
            } catch {
              return { ...base, state: "failed", error: "This answer could not be loaded." };
            }
          }),
        );
        if (live) setTurns(loaded);
      } catch (error) {
        if (live) setLoadError(problemText(error));
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => {
      live = false;
    };
  }, [conversationId]);

  useEffect(() => () => abort.current?.abort(), []);

  const ask = useCallback(
    async (question: string) => {
      const turn = newTurn(question);
      setTurns((all) => [...all, turn]);
      const update = (fn: (t: Turn) => Turn) =>
        setTurns((all) => all.map((t) => (t.id === turn.id ? fn(t) : t)));
      try {
        let id = idRef.current;
        if (id === null) {
          id = (await openConversation()).conversation_id;
          idRef.current = id;
          onCreated(id);
        }
        const accepted = await askQuestion(id, { question });
        abort.current = new AbortController();
        await streamRun(accepted.run_id, {
          signal: abort.current.signal,
          onEvent: (event) => update((t) => applyEvent(t, event)),
        });
      } catch (error) {
        update((t) => ({ ...t, state: "failed", error: problemText(error) }));
      }
    },
    [onCreated],
  );

  return { turns, loading, loadError, ask, running: turns.some((t) => t.state === "running") };
}
