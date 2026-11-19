"use client";
// One answer (plan §6.0 (3)–(5), MASTER v2): while running, a short human trace from the allow-listed events; when
// done, the answer with its number receipts, the refused part in a quiet box, and "How we know". Model text is plain
// text only (never HTML or Markdown), shown with dir="auto" so an Arabic answer reads right to left.
import {
  AlertTriangle,
  Check,
  ChevronDown,
  CircleSlash,
  Cpu,
  Database,
  HelpCircle,
  Loader2,
  Lock,
  Receipt,
  Sparkles,
} from "lucide-react";
import { ReceiptText } from "@/components/receipt/ReceiptText";
import { cn } from "@/lib/utils";
import type { Turn } from "./useAskThread";

const TOOL_LABELS: Record<string, string> = {
  finance_kpi: "Finance views",
  invoice_audit: "Invoice audit",
  search_documents: "Documents",
  web_search: "Web search",
  voyage_status: "Voyage status",
  voyage_eta: "Voyage ETA",
  watch_alerts: "Watch alerts",
  fleet_customers: "Fleet customers",
  sea_route: "Sea route",
  vessel_params: "Vessel data",
  marine_weather: "Marine weather",
  suez_transits: "Suez transits",
  route_advice: "Route advice",
};
export const toolLabel = (name: string) => TOOL_LABELS[name] ?? name;

const STATUS: Record<string, { note: string; tone: "ok" | "quiet" | "warn" }> = {
  answered: { note: "", tone: "ok" },
  partial: { note: "Part of this question is outside your access; the rest is answered.", tone: "ok" },
  not_permitted: { note: "This question is about data outside your access.", tone: "quiet" },
  not_in_data: { note: "PortPilot's data does not hold this.", tone: "quiet" },
  clarify: { note: "One question back before answering:", tone: "quiet" },
  ask_back: { note: "One question back before answering:", tone: "quiet" },
  output_invalid: {
    note: "The answer did not pass its checks, so it is not shown. Ask again or rephrase.",
    tone: "warn",
  },
  validation_failed: { note: "The answer did not pass its checks, so it is not shown.", tone: "warn" },
};

function Trace({ turn }: { turn: Turn }) {
  const steps = [
    {
      label: turn.queued !== undefined ? `Waiting in line (${turn.queued} ahead)` : "Checking your access",
      done: turn.queued === undefined,
    },
    ...turn.tools
      .filter((t) => t.state === "called")
      .map((t) => ({ label: `Reading ${toolLabel(t.name)}`, done: true })),
    { label: "Checking every number", done: Boolean(turn.answer) },
  ];
  return (
    <ol className="flex flex-wrap items-center gap-1.5" aria-label="What is being done" aria-live="polite">
      {steps.map((s, k) => (
        <li key={`${s.label}-${k}`} className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span
            className={cn(
              "grid size-4 place-items-center rounded-full",
              s.done ? "bg-primary text-primary-foreground" : "bg-accent text-primary",
            )}
          >
            {s.done ? (
              <Check className="size-3" aria-hidden />
            ) : (
              <Loader2 className="size-3 animate-spin" aria-hidden />
            )}
          </span>
          {s.label}
          {k < steps.length - 1 ? <span className="mx-1 h-px w-4 bg-border" aria-hidden /> : null}
        </li>
      ))}
    </ol>
  );
}

export function AnswerCard({ turn }: { turn: Turn }) {
  const a = turn.answer;
  const text = typeof a?.answer === "string" ? a.answer : null;
  const status = a?.status ?? (turn.state === "failed" ? "failed" : null);
  const meta = status ? STATUS[status] : undefined;
  const evidence = Object.entries(a?.evidence ?? {});

  return (
    <div className="flex flex-col gap-3">
      {turn.understood ? (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Sparkles className="size-3.5 text-primary" aria-hidden /> Understood as{" "}
          <span dir="auto" className="font-medium text-foreground">
            {turn.understood.text}
          </span>
        </p>
      ) : null}
      {turn.state === "running" || turn.tools.length ? <Trace turn={turn} /> : null}

      <div className="rounded-xl border bg-card px-6 py-5 shadow-sm">
        {turn.tools.length ? (
          <div className="mb-4 flex flex-wrap gap-1.5">
            {turn.tools.map((tool) => (
              <span
                key={`${tool.name}-${tool.state}`}
                className={cn(
                  "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-xs",
                  tool.state === "called"
                    ? "border-primary/25 bg-accent text-primary"
                    : "text-muted-foreground",
                )}
              >
                {tool.state === "called" ? (
                  <Database className="size-3" aria-hidden />
                ) : (
                  <CircleSlash className="size-3" aria-hidden />
                )}
                {tool.name}
                {tool.state === "refused" ? (
                  <span className="font-sans">· not part of your access</span>
                ) : null}
              </span>
            ))}
          </div>
        ) : null}

        {turn.state === "running" && !a ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Working on it…
          </p>
        ) : null}

        {turn.state === "failed" && !a ? (
          <p role="alert" className="flex items-start gap-2 text-sm text-alert-ink">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />{" "}
            {turn.error ?? "The answer could not be produced."}
          </p>
        ) : null}

        {meta?.note ? (
          <p
            className={cn(
              "mb-2 flex items-start gap-2 text-sm",
              meta.tone === "warn" ? "text-alert-ink" : "text-muted-foreground",
            )}
          >
            {status === "clarify" || status === "ask_back" ? (
              <HelpCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
            ) : null}
            {meta.note}
          </p>
        ) : null}

        {text && status !== "output_invalid" && status !== "validation_failed" ? (
          <p dir="auto" className="max-w-[68ch] text-[1.05rem] leading-8 whitespace-pre-line">
            <ReceiptText text={text} numbers={a?.numbers ?? []} />
          </p>
        ) : null}

        {a?.not_permitted?.length && status === "partial" ? (
          <div className="mt-4 flex gap-3 rounded-lg border border-dashed px-4 py-3">
            <Lock className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
            <p className="text-sm text-muted-foreground">
              Not part of your access: {a.not_permitted?.join(", ")}.
            </p>
          </div>
        ) : null}

        {a ? (
          <details className="group mt-4 border-t pt-3">
            <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium">
              <ChevronDown className="size-4 transition-transform group-open:rotate-180" aria-hidden /> How we
              know
              <span className="ms-auto flex items-center gap-3 text-xs font-normal text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Cpu className="size-3.5" aria-hidden /> {a.model_calls} model calls
                </span>
                {a.numbers?.length ? (
                  <span className="flex items-center gap-1">
                    <Receipt className="size-3.5" aria-hidden /> {a.numbers?.length} numbers with receipts
                  </span>
                ) : null}
              </span>
            </summary>
            {evidence.length ? (
              <ul className="mt-3 flex flex-col gap-2">
                {evidence.map(([id, e]) => (
                  <li
                    key={id}
                    className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border px-3 py-2 text-xs"
                  >
                    <span className="font-mono font-semibold">{id}</span>
                    <span className="font-mono text-muted-foreground">
                      {e.tool} → {e.source ?? "—"}
                    </span>
                    <span
                      className={cn(
                        "ms-auto rounded-full px-2 py-0.5 font-semibold",
                        e.status === "ok"
                          ? "bg-approved-wash text-approved-ink"
                          : "bg-muted text-muted-foreground",
                      )}
                    >
                      {e.status === "ok" ? "read" : (e.status ?? "—")}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-xs text-muted-foreground">No data source was needed for this answer.</p>
            )}
          </details>
        ) : null}
      </div>
    </div>
  );
}
