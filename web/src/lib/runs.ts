"use client";
// A run's events in the browser (Frontend plan §5): fetch + ReadableStream through the BFF (so Last-Event-ID can be
// sent on a reconnect), parsed by eventsource-parser, each event checked
// against the zod union generated from the API's RunEvent (an unknown event is logged and dropped, never rendered).
// A dropped stream reconnects with Last-Event-ID; when the run is over or the buffer is gone, GET /runs/{id} answers.
import { createParser, type EventSourceMessage } from "eventsource-parser";
import type { RunEventSchema, RunOut } from "@/api/generated/client";
import { RunEventsApiV1RunsRunIdEventsGetResponse as RunEventZ } from "@/api/generated/zod";
import { BffError, bffFetch } from "@/lib/bff/client";
import { observeRun } from "@/lib/run-recovery";

const MAX_RETRIES = 3;
const WATCH_TIMEOUT_MS = 360_000; // longer than the longest API run deadline (300 s)
const POLL_MS = 1_000;

export type RunHandlers = {
  onEvent: (event: RunEventSchema) => void;
  signal?: AbortSignal;
  recovery?: boolean;
};

export class RunObservationError extends Error {
  constructor() {
    super(
      "The request was accepted, but its progress could not be read. Use Resume progress above before submitting again.",
    );
  }
}

function pause(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    signal.throwIfAborted();
    const abort = () => {
      clearTimeout(timer);
      reject(signal.reason);
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", abort);
      resolve();
    }, ms);
    signal.addEventListener("abort", abort, { once: true });
  });
}

function parse(message: EventSourceMessage): RunEventSchema | null {
  try {
    const candidate = { id: Number(message.id), event: message.event, data: JSON.parse(message.data) };
    const ok = RunEventZ.safeParse(candidate);
    if (ok.success) return ok.data as RunEventSchema;
    console.warn("run event outside the contract, dropped", message.event);
  } catch {
    console.warn("unreadable run event, dropped");
  }
  return null;
}

/** Resolves only after a terminal event. Transport failure/expiry throws; it never means success. */
export async function streamRun(runId: string, handlers: RunHandlers): Promise<void> {
  const settle = handlers.recovery ? null : observeRun(runId);
  try {
    await watchRun(runId, handlers);
    settle?.(true);
  } catch (error) {
    settle?.(false);
    if (handlers.recovery || handlers.signal?.aborted) throw error;
    throw new RunObservationError();
  }
}

async function watchRun(runId: string, { onEvent, signal }: RunHandlers): Promise<void> {
  const deadline = AbortSignal.timeout(WATCH_TIMEOUT_MS);
  const watching = signal ? AbortSignal.any([signal, deadline]) : deadline;
  let last: number | null = null;
  let finished = false;
  function deliver(event: RunEventSchema) {
    if (finished || (last !== null && event.id <= last)) return;
    last = event.id;
    onEvent(event);
    if (event.event === "done" || event.event === "failed") finished = true;
  }
  for (let attempt = 0; attempt <= MAX_RETRIES && !finished; attempt++) {
    watching.throwIfAborted();
    if (attempt) await pause(250 * 2 ** (attempt - 1), watching);
    try {
      const res = await fetch(`/bff/runs/${encodeURIComponent(runId)}/events`, {
        headers: { accept: "text/event-stream", ...(last !== null ? { "last-event-id": String(last) } : {}) },
        credentials: "same-origin",
        cache: "no-store",
        signal: watching,
      });
      if (!res.ok || !res.body) break;
      const parser = createParser({
        onEvent(message) {
          const event = parse(message);
          if (!event) return;
          deliver(event);
        },
      });
      const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
      try {
        while (!finished) {
          const { value, done } = await reader.read();
          if (done) break;
          parser.feed(value);
        }
      } finally {
        await reader.cancel().catch(() => undefined);
        reader.releaseLock();
      }
    } catch (error) {
      watching.throwIfAborted();
      if (attempt === MAX_RETRIES) console.warn("run stream lost", error);
    }
  }
  let failures = 0;
  // A healthy GET can still say queued/running. Keep observing it until it actually ends.
  while (!finished) {
    watching.throwIfAborted();
    try {
      const run = await bffFetch<RunOut>(`/runs/${encodeURIComponent(runId)}`, { signal: watching });
      failures = 0;
      for (const candidate of run.events) {
        const event = RunEventZ.safeParse(candidate);
        if (event.success) deliver(event.data as RunEventSchema);
      }
    } catch (error) {
      watching.throwIfAborted();
      if (error instanceof BffError && error.status >= 400 && error.status < 500) throw error;
      if (++failures > MAX_RETRIES) throw error;
    }
    if (!finished) await pause(POLL_MS, watching);
  }
}
