// Number receipts (Frontend plan §6.0 (3), D-FE-1): the API will return, beside a rendered text, the spans of the
// numbers its slots filled. This turns (text, spans) into segments the UI renders as plain text + number chips.
// The shape is the one proposed for F0 (`answer_summary.numbers`); the concept uses it with sample data.

import type { NumberSpan as ApiNumberSpan } from "@/api/generated/client";

export type Trust = "database" | "untrusted_upload" | "web" | "document";

/** The API's span (generated from OpenAPI) + an optional trust label the UI may add from the evidence. */
export type NumberSpan = ApiNumberSpan & { trust?: Trust };

export type Segment = { kind: "text"; text: string } | { kind: "number"; span: NumberSpan };

/** Splits `text` by `spans`. A span that does not match its text, overlaps another or runs out of range is
 * dropped (the number then shows as plain text): a wrong receipt is worse than none. */
export function toSegments(text: string, spans: readonly NumberSpan[]): Segment[] {
  const ordered = [...spans].sort((a, b) => a.start - b.start);
  const out: Segment[] = [];
  let at = 0;
  for (const span of ordered) {
    const valid =
      Number.isInteger(span.start) &&
      Number.isInteger(span.end) &&
      span.start >= at &&
      span.end > span.start &&
      span.end <= text.length &&
      text.slice(span.start, span.end) === span.text;
    if (!valid) continue;
    if (span.start > at) out.push({ kind: "text", text: text.slice(at, span.start) });
    out.push({ kind: "number", span });
    at = span.end;
  }
  if (at < text.length) out.push({ kind: "text", text: text.slice(at) });
  return out;
}

/** Builds spans for sample data: finds each number's first occurrence after the previous one. Concept only —
 * real spans come from the API, never from searching the text in the browser. */
export function spansFor(
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
