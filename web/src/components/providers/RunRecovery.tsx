"use client";
import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { RunOut, ViewSpec } from "@/api/generated/client";
import { GetRunApiV1RunsRunIdGetResponse, ViewApiV1ViewsPostResponse } from "@/api/generated/zod";
import { Button } from "@/components/ui/button";
import { BffError, bffFetch } from "@/lib/bff/client";
import {
  forgetRun,
  pendingRuns,
  setRecoveryOwner,
  subscribeRecovery,
  type PendingRun,
} from "@/lib/run-recovery";
import { streamRun } from "@/lib/runs";

const AnswerCard = dynamic(() => import("@/components/ask/AnswerCard").then((m) => m.AnswerCard));
const ViewResult = dynamic(() => import("@/components/views/ViewsWorkspace").then((m) => m.ViewResult));

function destination(entry: PendingRun, run: RunOut | null): string {
  if (run?.kind === "route_advice" && run.thread_id) return `/routes/${encodeURIComponent(run.thread_id)}`;
  if (run?.kind.startsWith("pack_") && run.thread_id) return `/packs/${encodeURIComponent(run.thread_id)}`;
  if (run?.kind === "ask" && run.conversation_id) return `/ask/${encodeURIComponent(run.conversation_id)}`;
  return entry.path;
}

function RecoveryItem({ entry }: { entry: PendingRun }) {
  const label = entry.path.startsWith("/ask")
    ? "Question"
    : entry.path.startsWith("/routes")
      ? "Route comparison"
      : entry.path.startsWith("/views")
        ? "Chart"
        : "Pack review";
  const [busy, setBusy] = useState(false);
  const [run, setRun] = useState<RunOut | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort(), []);
  async function resume() {
    setBusy(true);
    setNote(null);
    const controller = new AbortController();
    abort.current = controller;
    const read = async () =>
      GetRunApiV1RunsRunIdGetResponse.parse(
        await bffFetch(`/runs/${encodeURIComponent(entry.id)}`, {
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(30_000)]),
        }),
      ) as RunOut;
    try {
      let current = await read();
      if (current.state === "queued" || current.state === "running") {
        await streamRun(entry.id, { recovery: true, signal: controller.signal, onEvent: () => undefined });
        current = await read();
      }
      if (controller.signal.aborted) return;
      setRun(current);
      setNote(
        current.state === "failed" ? (current.error?.detail ?? "The request failed.") : "Result recovered.",
      );
    } catch (error) {
      if (controller.signal.aborted) return;
      setNote(
        error instanceof BffError && [403, 404].includes(error.status)
          ? "Progress is no longer available. Open the saved page to check its outcome before submitting again."
          : "Progress could not be read. Resume again when the connection returns.",
      );
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  const view = ViewApiV1ViewsPostResponse.safeParse(run?.result?.view);
  const proposal =
    run?.kind === "pack_request" && typeof run.result?.answer === "object" ? run.result.answer : null;
  return (
    <section
      aria-label="Recover accepted request"
      className="min-w-0 rounded-lg border bg-card p-4 text-sm shadow-sm"
    >
      <p className="font-semibold">
        {run ? "Recovered request" : "Check your last request"} · {label}
      </p>
      <p className="mt-1 text-muted-foreground">Resume to check its outcome before submitting again.</p>
      {note ? (
        <p role="status" className="mt-2" dir="auto">
          {note}
        </p>
      ) : null}
      {run?.kind === "ask" && run.result ? (
        <AnswerCard
          turn={{ id: entry.id, question: "", state: "done", nodes: [], tools: [], answer: run.result }}
        />
      ) : null}
      {run?.kind === "view" && view.success ? <ViewResult spec={view.data as ViewSpec} /> : null}
      {run?.kind === "view" && !view.success && typeof run.result?.answer === "string" ? (
        <p dir="auto" className="mt-2">
          {run.result.answer}
        </p>
      ) : null}
      {proposal ? (
        <div className="mt-2">
          <p dir="auto">{String(proposal.ask_back ?? proposal.understood ?? "Request interpreted.")}</p>
          <p className="text-muted-foreground">
            Nothing was applied. Return to the pack and review your request again before confirming.
          </p>
        </div>
      ) : null}
      {run?.kind === "pack_decision" ? (
        <p className="mt-2">Open the pack to review its current state.</p>
      ) : null}
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Button size="sm" disabled={busy} onClick={() => void resume()}>
          {busy ? "Watching progress…" : run ? "Refresh result" : "Resume progress"}
        </Button>
        <a className="text-primary underline" href={destination(entry, run)}>
          Open saved page
        </a>
        <Button variant="ghost" size="sm" disabled={busy} onClick={() => forgetRun(entry.id)}>
          Dismiss reminder
        </Button>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        Dismissing this reminder does not cancel the request.
      </p>
    </section>
  );
}

export function RunRecovery({ employeeId }: { employeeId: number }) {
  const [entries, setEntries] = useState<PendingRun[]>([]);
  useEffect(() => {
    const refresh = () => setEntries(pendingRuns());
    const unsubscribe = subscribeRecovery(refresh);
    setRecoveryOwner(employeeId);
    refresh();
    return unsubscribe;
  }, [employeeId]);
  if (!entries.length) return null;
  return (
    <aside
      aria-label="Request recovery"
      className="mx-auto flex w-full max-w-7xl flex-col gap-3 p-4 text-foreground"
    >
      {entries.map((entry) => (
        <RecoveryItem key={`${employeeId}:${entry.id}`} entry={entry} />
      ))}
    </aside>
  );
}
