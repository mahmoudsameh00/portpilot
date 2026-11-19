import { expect, test } from "@playwright/test";
import { streamRun } from "../src/lib/runs";
import type { RunEventSchema } from "../src/api/generated/client";

const queued: RunEventSchema = { id: 1, event: "queued", data: { position: 1 } };
const done: RunEventSchema = { id: 2, event: "done", data: { status: "ok" } };
const originalFetch = globalThis.fetch;
test.afterEach(() => {
  globalThis.fetch = originalFetch;
});

test("stream loss polls a still-running backend until terminal, without duplicate events", async () => {
  let polls = 0;
  globalThis.fetch = async (input) => {
    if (String(input).endsWith("/events")) return new Response(null, { status: 503 });
    polls++;
    return Response.json({
      state: polls < 3 ? "running" : "done",
      events: polls < 3 ? [queued] : [queued, done],
    });
  };
  const seen: number[] = [];
  await streamRun("r", { onEvent: (event) => seen.push(event.id) });
  expect(polls).toBe(3);
  expect(seen).toEqual([1, 2]);
});

test("reconnect uses Last-Event-ID and ignores replayed events", async () => {
  let streams = 0;
  const ids: string[] = [];
  const sse = (event: RunEventSchema) =>
    `id: ${event.id}\nevent: ${event.event}\ndata: ${JSON.stringify(event.data)}\n\n`;
  globalThis.fetch = async (_input, init) => {
    streams++;
    ids.push(new Headers(init?.headers).get("last-event-id") ?? "");
    return new Response(sse(queued) + (streams > 1 ? sse(done) : ""));
  };
  const seen: number[] = [];
  await streamRun("r", { onEvent: (event) => seen.push(event.id) });
  expect(ids).toEqual(["", "1"]);
  expect(seen).toEqual([1, 2]);
});

test("cancellation during polling stops observation instead of reporting success", async () => {
  const controller = new AbortController();
  let polls = 0;
  globalThis.fetch = async (input) => {
    if (String(input).endsWith("/events")) return new Response(null, { status: 503 });
    polls++;
    return Response.json({ state: "running", events: [queued] });
  };
  await expect(
    streamRun("r", { signal: controller.signal, onEvent: () => controller.abort() }),
  ).rejects.toThrow();
  expect(polls).toBe(1);
});

test("transient polling failure recovers and a terminal failure is delivered once", async () => {
  let polls = 0;
  const failed: RunEventSchema = {
    id: 2,
    event: "failed",
    data: { type: "timeout", status: 504, detail: "expired" },
  };
  globalThis.fetch = async (input) => {
    if (String(input).endsWith("/events")) return new Response(null, { status: 503 });
    if (++polls === 1) throw new TypeError("offline");
    return Response.json({ state: "failed", events: [queued, failed, failed] });
  };
  const seen: string[] = [];
  await streamRun("r", { onEvent: (event) => seen.push(event.event) });
  expect(seen).toEqual(["queued", "failed"]);
});
