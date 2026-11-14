"use client";
// One pack, reviewed like slides (Frontend plan §6.0 (6), §6.4; MASTER v2): the filmstrip, the current slide as a
// replica of the PPTX (its bullets with their index and the charts the deck draws), the Validator's notes pinned to
// their bullet, the banners (degraded, redrafted, readiness), the log, the downloads, and the decision panel.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Download, FileClock, Info, Loader2, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { getPackApiV1PacksThreadIdGet as getPack } from "@/api/generated/client";
import { decideApiV1PacksThreadIdDecisionPostBodyAdditionsItemTextMax as MAX_ADDITION } from "@/api/generated/zod";
import { StatusBadge } from "@/components/concept/StatusBadge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { DecisionPanel, type Bullet } from "./DecisionPanel";
import { PackChart, type DrawnChart } from "./PackChart";
import { PublicationSync } from "./PublicationSync";

type Problem = { rule?: string; slide?: number | null; bullet?: number | null; message?: string };
type Draft = { title: string; slide_titles: { slide: number; title: string }[]; bullets: Bullet[] };

export function PackReview({ thread }: { thread: string }) {
  const qc = useQueryClient();
  const [slide, setSlide] = useState(2);
  const {
    data: pack,
    isPending,
    error,
  } = useQuery({ queryKey: ["pack", thread], queryFn: () => getPack(thread) });

  if (isPending)
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Loading the pack…
      </p>
    );
  if (error || !pack)
    return (
      <p role="alert" className="text-sm text-alert-ink">
        This pack is not available.
      </p>
    );

  const draft = pack.draft as Draft | null;
  const problems = (pack.validator_problems ?? []) as Problem[];
  const charts = (pack.charts_drawn?.[String(slide)] ?? []) as DrawnChart[];
  const titles = draft?.slide_titles ?? [];
  const noted = new Set(problems.map((p) => p.slide).filter((s): s is number => typeof s === "number"));
  const waiting = pack.next.length > 0;
  const status = pack.published ? "approved" : pack.status === "rejected" ? "rejected" : "draft";
  const base = `/bff/packs/${encodeURIComponent(thread)}`;
  const log = (pack.approval_log ?? []) as {
    at?: string;
    outcome?: string;
    decision?: string;
    reason?: string;
  }[];

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="me-auto">
          <p className="text-sm text-muted-foreground">Weekly finance pack</p>
          <h1 className="font-mono text-2xl font-semibold">
            {pack.week ? `2025-W${String(pack.week).padStart(2, "0")}` : thread}
          </h1>
        </div>
        {status === "rejected" ? (
          <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-semibold text-muted-foreground">
            Rejected
          </span>
        ) : (
          <StatusBadge kind={status === "approved" ? "approved" : "draft"} />
        )}
        {pack.has_preview ? (
          <a
            href={`${base}/preview`}
            className="inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium text-primary hover:bg-accent"
          >
            <Download className="size-4" aria-hidden /> Preview PowerPoint
          </a>
        ) : null}
        {pack.published ? (
          <a
            href={`${base}/deck`}
            className="inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium text-primary hover:bg-accent"
          >
            <Download className="size-4" aria-hidden /> Published deck
          </a>
        ) : null}
      </div>

      {pack.published ? <PublicationSync status={pack.publication_sync} /> : null}
      {pack.redrafted ? (
        <p className="flex gap-2 rounded-lg border border-waiting/40 bg-waiting-wash px-4 py-3 text-sm text-waiting-ink">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden /> The deck was drafted again. Earlier edits
          and additions were not carried over — add again what you still want.
        </p>
      ) : null}
      {pack.degraded ? (
        <p className="flex gap-2 rounded-lg border px-4 py-3 text-sm text-muted-foreground">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden /> Some texts were written by code
          because the writer&apos;s text did not pass its checks.
        </p>
      ) : null}
      {pack.readiness.length ? (
        <ul className="rounded-lg border px-4 py-3 text-sm text-muted-foreground">
          {pack.readiness.map((r, i) => (
            <li key={i}>{String(r)}</li>
          ))}
        </ul>
      ) : null}

      {draft ? (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[13rem_minmax(0,1fr)_22rem]">
          <nav aria-label="Slides" className="order-2 min-w-0 lg:order-none">
            <ol className="flex gap-2 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible lg:pb-0">
              {titles.map((t) => (
                <li key={t.slide} className="shrink-0">
                  <button
                    type="button"
                    onClick={() => setSlide(t.slide)}
                    aria-current={t.slide === slide ? "true" : undefined}
                    className={cn(
                      "flex w-44 items-start gap-2 rounded-lg border px-2.5 py-2 text-start text-sm transition-colors lg:w-full",
                      t.slide === slide
                        ? "border-primary bg-card font-medium shadow-sm"
                        : "border-transparent text-muted-foreground hover:bg-card",
                    )}
                  >
                    <span className="num w-5 shrink-0 font-mono text-xs text-muted-foreground">
                      {t.slide}
                    </span>
                    <span className="line-clamp-3 flex-1 leading-snug">{t.title}</span>
                    {noted.has(t.slide) ? (
                      <TriangleAlert className="size-4 shrink-0 text-waiting" aria-label="Validator note" />
                    ) : null}
                  </button>
                </li>
              ))}
            </ol>
          </nav>

          <section className="min-w-0" aria-label={`Slide ${slide}`}>
            <div className="w-full rounded-xl border bg-white p-6 text-navy shadow-float">
              <h2 className="text-xl font-bold">{titles.find((t) => t.slide === slide)?.title}</h2>
              <ul className="mt-4 flex flex-col gap-3 text-sm">
                {draft.bullets.map((b, i) =>
                  b.slide !== slide ? null : (
                    <li
                      key={i}
                      className={cn(
                        "border-s-2 ps-3 leading-relaxed",
                        problems.some((p) => p.bullet === i)
                          ? "border-waiting bg-waiting-wash/70"
                          : "border-chart-1",
                      )}
                    >
                      <span className="me-2 font-mono text-xs text-muted-foreground">{i}</span>
                      <span dir="auto">{b.text}</span>
                      {b.origin === "approver" ? (
                        <span className="ms-2 rounded bg-accent px-1.5 py-0.5 text-[0.7rem] text-primary">
                          Approver&apos;s addition
                        </span>
                      ) : null}
                    </li>
                  ),
                )}
              </ul>
              {charts.map((c) => (
                <div key={c.name} className="mt-5">
                  <PackChart chart={c} />
                </div>
              ))}
            </div>
            {problems
              .filter((p) => p.slide === slide || (p.slide === null && slide === 2))
              .map((p, i) => (
                <p
                  key={i}
                  className="mt-3 flex gap-2 rounded-lg border border-waiting/40 bg-waiting-wash px-4 py-3 text-sm text-waiting-ink"
                >
                  <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                  <span>
                    <span className="font-semibold">Validator {p.rule}</span>
                    {typeof p.bullet === "number" ? ` (bullet ${p.bullet})` : ""}: {p.message}
                  </span>
                </p>
              ))}
          </section>

          <Card className="order-3 self-start lg:order-none">
            <CardHeader>
              <CardTitle className="text-base">{pack.allowed.decide ? "Your decision" : "Status"}</CardTitle>
              <CardDescription>
                {pack.allowed.decide
                  ? "Every change is checked again before the deck is rebuilt."
                  : waiting
                    ? "Waiting for a Finance manager or the CEO."
                    : "This pack no longer waits for a decision."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {pack.allowed.decide ? (
                <DecisionPanel
                  thread={thread}
                  draftSha={pack.draft_sha}
                  allowed={pack.allowed}
                  bullets={draft.bullets}
                  slide={slide}
                  limits={{
                    max_chart_changes: pack.allowed.max_chart_changes,
                    max_analysis_edits: pack.allowed.max_analysis_edits,
                    max_steer_chars: pack.allowed.max_steer_chars,
                    max_addition_chars: MAX_ADDITION,
                  }}
                  insight={pack.insight as { summary?: { text: string }[]; caveats?: string[] } | null}
                  onDone={() => void qc.invalidateQueries({ queryKey: ["pack", thread] })}
                />
              ) : null}
            </CardContent>
          </Card>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">This pack has no draft yet.</p>
      )}

      {log.length ? (
        <section aria-label="Decisions so far">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <FileClock className="size-4" aria-hidden /> Decisions so far
          </h2>
          <ul className="mt-2 flex flex-col gap-1 text-sm text-muted-foreground">
            {log.map((e, i) => (
              <li key={i}>
                <span className="font-mono text-xs">{e.at?.slice(0, 16).replace("T", " ")}</span> —{" "}
                {e.outcome}
                {e.reason ? `: ${e.reason}` : ""}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
