import { expect, test } from "@playwright/test";
import { toSegments, type NumberSpan } from "../src/lib/receipts";

/** Test helper: spans for hand-written text — each number's first occurrence after the previous one (real spans come
 * from the API, never from searching the text in the browser). */
function spansFor(
  text: string,
  numbers: ReadonlyArray<Omit<NumberSpan, "start" | "end" | "row"> & { row?: number | null }>,
): NumberSpan[] {
  let from = 0;
  return numbers.flatMap((n) => {
    const start = text.indexOf(n.text, from);
    if (start < 0) return [];
    from = start + n.text.length;
    return [{ ...n, row: n.row ?? null, start, end: from }];
  });
}

const base = {
  evidence_id: "kpi.weekly",
  field: "billed_sdr",
  source: "finance.finance_kpi",
  filter: null,
  row: 0,
} as const;

test("numbers become chips at their offsets, the rest stays text", () => {
  const text = "Billed 8,394,785.98 SDR in W23, 3.4% above budget.";
  const spans = spansFor(text, [
    { ...base, text: "8,394,785.98 SDR" },
    { ...base, text: "3.4%", field: "billed_vs_budget_pct" },
  ]);
  const segs = toSegments(text, spans);
  expect(segs.map((s) => s.kind)).toEqual(["text", "number", "text", "number", "text"]);
  expect(segs.map((s) => (s.kind === "text" ? s.text : s.span.text)).join("")).toBe(text);
});

test("a span that does not match its text, overlaps or runs out of range is dropped", () => {
  const text = "Collected 3,611,204.75 SDR.";
  const good: NumberSpan = { ...base, text: "3,611,204.75 SDR", start: 10, end: 26 };
  const wrongText: NumberSpan = { ...good, text: "9,999,999.99 SDR" };
  const overlap: NumberSpan = { ...good, start: 12, end: 20, text: text.slice(12, 20) };
  const outOfRange: NumberSpan = { ...good, start: 20, end: 99 };
  const segs = toSegments(text, [good, wrongText, overlap, outOfRange]);
  expect(segs.filter((s) => s.kind === "number")).toHaveLength(1);
  expect(segs.map((s) => (s.kind === "text" ? s.text : s.span.text)).join("")).toBe(text);
});

test("Arabic text keeps its order around the numbers", () => {
  const text = "فوترت PortPilot مبلغ 8,394,785.98 SDR في أسبوع 23.";
  const segs = toSegments(text, spansFor(text, [{ ...base, text: "8,394,785.98 SDR" }]));
  expect(segs).toHaveLength(3);
  expect(segs[1]?.kind).toBe("number");
});

import { applyEvent, type Turn } from "../src/components/ask/useAskThread";

test("run events fold into a turn in order; a refused tool is kept apart from the called ones", () => {
  let t: Turn = { id: "t", question: "q", state: "running", nodes: [], tools: [] };
  t = applyEvent(t, { id: 1, event: "queued", data: { position: 2 } });
  expect(t.queued).toBe(2);
  t = applyEvent(t, { id: 2, event: "started", data: { thread_id: "ask:1", graph: "ask" } });
  t = applyEvent(t, { id: 3, event: "tool_called", data: { name: "finance_kpi" } });
  t = applyEvent(t, { id: 4, event: "tool_called", data: { name: "finance_kpi" } });
  t = applyEvent(t, {
    id: 5,
    event: "tool_refused",
    data: { name: "employee_directory", part: "HR headcount" },
  });
  expect(t.queued).toBeUndefined();
  expect(t.tools).toEqual([
    { name: "finance_kpi", state: "called" },
    { name: "employee_directory", state: "refused", part: "HR headcount" },
  ]);
  t = applyEvent(t, {
    id: 6,
    event: "failed",
    data: { type: "timeout", status: 504, detail: "the run took too long" },
  });
  expect(t.state).toBe("failed");
  expect(t.error).toBe("the run took too long");
});
