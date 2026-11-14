"use client";
// The approver's decision (Frontend plan §6.4 + D-FE-9): a request in words (understood → steps → Confirm), or the
// structured kinds — edit (text, additions, charts), revise (steer, a caveat), approve, reject. Every body is checked
// first by the same rules the API applies (src/lib/decision.ts); the API and the graph check again.
import {
  CheckCircle2,
  Loader2,
  MessageSquareText,
  PencilLine,
  RotateCcw,
  ShieldCheck,
  XCircle,
  BarChart3,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { useState } from "react";
import {
  catalogueApiV1ChartsCatalogueGet as getCatalogue,
  confirmRequestApiV1PacksThreadIdRequestConfirmPost as confirmRequest,
  decideApiV1PacksThreadIdDecisionPost as decide,
  readRequestApiV1PacksThreadIdRequestPost as sendRequest,
  type ChartChoice,
  type DecisionIn,
  type PackAllowed,
  type RunAccepted,
  type RunEventSchema,
} from "@/api/generated/client";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BffError } from "@/lib/bff/client";
import { decisionProblem, type Limits } from "@/lib/decision";
import { RunObservationError, streamRun } from "@/lib/runs";
import { cn } from "@/lib/utils";

// React Flow only in the browser and only when a decision runs (plan §6.8)
const RunGraph = dynamic(() => import("./RunGraph").then((m) => m.RunGraph), { ssr: false });

export type Bullet = { slide: number; text: string; origin?: string | null };

type Proposal = {
  understood: string;
  steps: DecisionIn[];
  ask_back?: string | null;
  draft_sha: string;
  reread_text?: boolean;
};

const STEP_WORDS: Record<string, string> = {
  approve: "approve the pack",
  reject: "reject the pack",
  edit: "edit the deck",
  revise: "revise the analysis and draft the deck again",
};

function describe(step: DecisionIn): string {
  const parts = [
    step.edits?.length ? `${step.edits.length} text edit(s)` : null,
    step.additions?.length ? `${step.additions.length} new bullet(s)` : null,
    step.charts?.length ? `${step.charts.length} chart change(s)` : null,
    step.analysis_edits?.length ? `${step.analysis_edits.length} analysis edit(s)` : null,
    step.steer ? `steer: “${step.steer}”` : null,
  ].filter(Boolean);
  return `${STEP_WORDS[step.decision] ?? step.decision}${parts.length ? ` — ${parts.join(", ")}` : ""}`;
}

function problemOf(error: unknown): string {
  if (error instanceof RunObservationError) return error.message;
  if (error instanceof BffError) {
    if (error.status === 409)
      return "The pack changed or another decision is in progress. Reload and review it before trying again.";
    if (error.status === 403) return "Only a Finance manager or the CEO decides a pack.";
    return error.title;
  }
  return "The decision could not be sent. Try again.";
}

type Insight = { summary?: { text: string }[]; caveats?: string[] };
type Named = Record<string, { name: string; unit: string }>;
type PackCatalogue = {
  trend: { series: Named; weeks: number[]; max_series: number };
  variance: { measure: Named; rows: string[] };
};
const selectClass = "h-9 w-full rounded-md border bg-background px-2 text-sm focus-visible:border-primary";

export function DecisionPanel({
  thread,
  draftSha,
  allowed,
  bullets,
  slide,
  limits,
  insight,
  onDone,
}: {
  thread: string;
  draftSha: string;
  allowed: PackAllowed;
  bullets: Bullet[];
  slide: number;
  limits: Limits;
  insight?: Insight | null;
  onDone: () => void;
}) {
  const catalogue = useQuery({ queryKey: ["catalogue"], queryFn: () => getCatalogue() });
  const packCat = catalogue.data?.pack as PackCatalogue | undefined;
  const [chartKind, setChartKind] = useState<"trend" | "variance">("trend");
  const [trendSeries, setTrendSeries] = useState<string[]>(["billed_sdr", "budget_sdr"]);
  const [trendWeeks, setTrendWeeks] = useState(13);
  const [varMeasure, setVarMeasure] = useState("budget_variance_sdr");
  const [varRows, setVarRows] = useState("all");
  const [summaryEdits, setSummaryEdits] = useState<Record<number, string>>({});
  const [caveat, setCaveat] = useState("");
  const [busy, setBusy] = useState(false);
  const [trace, setTrace] = useState<string[]>([]);
  const [graphRun, setGraphRun] = useState(false);
  const [message, setMessage] = useState<{ tone: "ok" | "warn"; text: string } | null>(null);
  const [edits, setEdits] = useState<Record<number, string>>({});
  const [addition, setAddition] = useState("");
  const [steer, setSteer] = useState("");
  const [comment, setComment] = useState("");
  const [request, setRequest] = useState("");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [formVersion, setFormVersion] = useState(draftSha);
  // A background refresh must not attach old edits to a newer review version.
  if (formVersion !== draftSha) {
    setFormVersion(draftSha);
    setEdits({});
    setSummaryEdits({});
    setAddition("");
    setSteer("");
    setCaveat("");
    setComment("");
    setRequest("");
    setProposal(null);
    setChartKind("trend");
    setTrendSeries(["billed_sdr", "budget_sdr"]);
    setTrendWeeks(13);
    setVarMeasure("budget_variance_sdr");
    setVarRows("all");
  }

  async function run(
    start: () => Promise<RunAccepted>,
    onAnswer?: (answer: unknown) => void,
    graph = false, // a decision that runs the pack graph: shown as the React Flow view
  ) {
    setBusy(true);
    setTrace([]);
    setGraphRun(graph);
    setMessage(null);
    try {
      const accepted = await start();
      let failed: string | null = null;
      await streamRun(accepted.run_id, {
        onEvent: (e: RunEventSchema) => {
          if (e.event === "node" && e.data.phase === "start") setTrace((t) => [...t, e.data.name]);
          if (e.event === "answer") onAnswer?.(e.data.answer);
          if (e.event === "failed") failed = e.data.detail;
        },
      });
      if (failed) setMessage({ tone: "warn", text: failed });
      return !failed;
    } catch (error) {
      setMessage({ tone: "warn", text: problemOf(error) });
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function submit(body: DecisionIn) {
    const problem = decisionProblem(body as unknown as Record<string, unknown>, limits);
    if (problem) {
      setMessage({ tone: "warn", text: problem });
      return;
    }
    const ok = await run(() => decide(thread, { ...body, draft_sha: draftSha }), undefined, true);
    if (ok) {
      setEdits({});
      setAddition("");
      setSteer("");
      setMessage({ tone: "ok", text: `Sent: ${STEP_WORDS[body.decision] ?? body.decision}.` });
      onDone();
    }
  }

  const slideBullets = bullets.map((b, i) => ({ ...b, index: i })).filter((b) => b.slide === slide);
  const canAdd = allowed.addition_slides.includes(slide);
  const additionsHere = slideBullets.filter((b) => b.origin === "approver").length;

  return (
    <div className="flex flex-col gap-4">
      <Tabs defaultValue="request">
        <TabsList className="w-full">
          <TabsTrigger value="request">Request</TabsTrigger>
          <TabsTrigger value="edit">Edit</TabsTrigger>
          <TabsTrigger value="chart">Chart</TabsTrigger>
          <TabsTrigger value="revise">Revise</TabsTrigger>
          <TabsTrigger value="decide">Decide</TabsTrigger>
        </TabsList>

        <TabsContent value="request" className="mt-3 flex flex-col gap-2">
          <label htmlFor="request" className="text-xs text-muted-foreground">
            Say what to change, in English or Arabic. Nothing changes until you confirm.
          </label>
          <textarea
            id="request"
            dir="auto"
            rows={3}
            maxLength={500}
            value={request}
            onChange={(e) => {
              setRequest(e.target.value);
              setProposal(null);
            }}
            className="w-full resize-y rounded-md border bg-background p-3 text-sm focus-visible:border-primary"
          />
          <Button
            variant="outline"
            size="sm"
            disabled={busy || request.trim().length < 3}
            onClick={() =>
              run(
                () => sendRequest(thread, { request: request.trim() }),
                (a) => setProposal(a as Proposal),
              )
            }
          >
            <MessageSquareText aria-hidden /> Understand my request
          </Button>
          {proposal ? (
            <div className="rounded-lg border bg-accent/60 p-3 text-sm" aria-live="polite">
              <p className="text-xs text-muted-foreground">Understood as</p>
              <p dir="auto" className="mt-0.5 font-medium">
                {proposal.understood}
              </p>
              {proposal.ask_back ? (
                <p dir="auto" className="mt-2 text-waiting-ink">
                  {proposal.ask_back}
                </p>
              ) : (
                <>
                  <ol className="mt-2 list-decimal ps-5 text-xs text-muted-foreground">
                    {proposal.steps.map((s, i) => (
                      <li key={i}>{describe(s)}</li>
                    ))}
                  </ol>
                  <Button
                    size="sm"
                    className="mt-3"
                    disabled={busy}
                    onClick={async () => {
                      const ok = await run(
                        () =>
                          confirmRequest(thread, {
                            request: request.trim(),
                            proposal: {
                              understood: proposal.understood,
                              steps: proposal.steps,
                              draft_sha: proposal.draft_sha,
                              reread_text: proposal.reread_text ?? false,
                            },
                          }),
                        undefined,
                        true,
                      );
                      if (ok) {
                        setProposal(null);
                        setRequest("");
                        setMessage({ tone: "ok", text: "Applied. The deck was checked again." });
                        onDone();
                      }
                    }}
                  >
                    <CheckCircle2 aria-hidden /> Confirm
                  </Button>
                </>
              )}
            </div>
          ) : null}
        </TabsContent>

        <TabsContent value="edit" className="mt-3 flex flex-col gap-3">
          <p className="text-xs text-muted-foreground">
            Slide {slide}: change a bullet&apos;s words, or add your own.
          </p>
          {slideBullets.map((b) => (
            <div key={b.index}>
              <label htmlFor={`b${b.index}`} className="text-xs text-muted-foreground">
                Bullet {b.index}
                {b.origin === "approver" ? " · your addition" : ""}
              </label>
              <textarea
                id={`b${b.index}`}
                dir="auto"
                rows={2}
                maxLength={600}
                defaultValue={b.text}
                onChange={(e) => setEdits((all) => ({ ...all, [b.index]: e.target.value }))}
                className="mt-1 w-full resize-y rounded-md border bg-background p-2 text-sm focus-visible:border-primary"
              />
            </div>
          ))}
          {canAdd && additionsHere < allowed.max_additions ? (
            <div>
              <label htmlFor="addition" className="text-xs text-muted-foreground">
                Add a bullet to slide {slide} (its numbers must match this slide&apos;s evidence)
              </label>
              <textarea
                id="addition"
                dir="auto"
                rows={2}
                maxLength={limits.max_addition_chars}
                value={addition}
                onChange={(e) => setAddition(e.target.value)}
                className="mt-1 w-full resize-y rounded-md border bg-background p-2 text-sm focus-visible:border-primary"
              />
            </div>
          ) : null}
          <Button
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={() =>
              submit({
                decision: "edit",
                edits: Object.entries(edits)
                  .filter(([i, t]) => t.trim() && t !== bullets[Number(i)]?.text)
                  .map(([i, t]) => ({ bullet: Number(i), text: t.trim() })),
                additions: addition.trim() ? [{ slide, text: addition.trim() }] : [],
              })
            }
          >
            <PencilLine aria-hidden /> Save and check again
          </Button>
        </TabsContent>

        <TabsContent value="revise" className="mt-3 flex flex-col gap-2">
          <p className="text-xs text-muted-foreground">
            The analysis is redone and the deck drafted again. {allowed.revise_left} revision(s) left for this
            pack.
          </p>
          <label htmlFor="steer" className="text-xs text-muted-foreground">
            What should the analysis focus on?
          </label>
          <textarea
            id="steer"
            dir="auto"
            rows={3}
            maxLength={allowed.max_steer_chars}
            value={steer}
            onChange={(e) => setSteer(e.target.value)}
            className="w-full resize-y rounded-md border bg-background p-3 text-sm focus-visible:border-primary"
          />
          {insight?.summary?.length ? (
            <fieldset className="flex flex-col gap-2">
              <legend className="text-xs text-muted-foreground">Summary points (change the wording)</legend>
              {insight.summary.map((p, i) => (
                <textarea
                  key={i}
                  aria-label={`Summary point ${i + 1}`}
                  dir="auto"
                  rows={2}
                  maxLength={400}
                  defaultValue={p.text}
                  onChange={(e) => setSummaryEdits((all) => ({ ...all, [i]: e.target.value }))}
                  className="w-full resize-y rounded-md border bg-background p-2 text-xs focus-visible:border-primary"
                />
              ))}
            </fieldset>
          ) : null}
          <label htmlFor="caveat" className="text-xs text-muted-foreground">
            Add a caveat
          </label>
          <textarea
            id="caveat"
            dir="auto"
            rows={2}
            maxLength={400}
            value={caveat}
            onChange={(e) => setCaveat(e.target.value)}
            className="w-full resize-y rounded-md border bg-background p-2 text-sm focus-visible:border-primary"
          />
          <Button
            variant="outline"
            size="sm"
            disabled={busy || allowed.revise_left === 0}
            onClick={() => {
              const analysis_edits = [
                ...Object.entries(summaryEdits)
                  .filter(([i, t]) => t.trim() && t !== insight?.summary?.[Number(i)]?.text)
                  .map(([i, t]) => ({
                    target: "summary" as const,
                    op: "replace" as const,
                    index: Number(i),
                    text: t.trim(),
                  })),
                ...(caveat.trim()
                  ? [{ target: "caveat" as const, op: "add" as const, text: caveat.trim() }]
                  : []),
              ];
              void submit({
                decision: "revise",
                ...(steer.trim() ? { steer: steer.trim() } : {}),
                ...(analysis_edits.length ? { analysis_edits } : {}),
              });
            }}
          >
            <RotateCcw aria-hidden /> Revise
          </Button>
        </TabsContent>

        <TabsContent value="chart" className="mt-3 flex flex-col gap-3 text-sm">
          <p className="text-xs text-muted-foreground">
            Change how a chart of the deck is drawn (from the catalogue).
          </p>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">Chart</span>
            <select
              className={selectClass}
              value={chartKind}
              onChange={(e) => setChartKind(e.target.value as "trend" | "variance")}
            >
              <option value="trend">The 13-week trend</option>
              <option value="variance">Billed against budget by category</option>
            </select>
          </label>
          {chartKind === "trend" && packCat ? (
            <>
              <fieldset className="flex flex-col gap-1">
                <legend className="text-xs text-muted-foreground">
                  Series (up to {packCat.trend.max_series}, one unit)
                </legend>
                {Object.entries(packCat.trend.series).map(([k, s]) => {
                  const on = trendSeries.includes(k);
                  const unit = trendSeries[0] ? packCat.trend.series[trendSeries[0]]?.unit : undefined;
                  const blocked =
                    !on &&
                    (trendSeries.length >= packCat.trend.max_series ||
                      (unit !== undefined && s.unit !== unit));
                  return (
                    <label key={k} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={on}
                        disabled={blocked}
                        onChange={() =>
                          setTrendSeries((all) => (on ? all.filter((x) => x !== k) : [...all, k]))
                        }
                      />
                      {s.name}
                    </label>
                  );
                })}
              </fieldset>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-muted-foreground">Weeks shown</span>
                <select
                  className={selectClass}
                  value={trendWeeks}
                  onChange={(e) => setTrendWeeks(Number(e.target.value))}
                >
                  {packCat.trend.weeks.map((w) => (
                    <option key={w} value={w}>
                      {w} weeks
                    </option>
                  ))}
                </select>
              </label>
            </>
          ) : null}
          {chartKind === "variance" && packCat ? (
            <>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-muted-foreground">Measure</span>
                <select
                  className={selectClass}
                  value={varMeasure}
                  onChange={(e) => setVarMeasure(e.target.value)}
                >
                  {Object.entries(packCat.variance.measure).map(([k, m]) => (
                    <option key={k} value={k}>
                      {m.name} ({m.unit})
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-muted-foreground">Rows</span>
                <select className={selectClass} value={varRows} onChange={(e) => setVarRows(e.target.value)}>
                  {packCat.variance.rows.map((r) => (
                    <option key={r} value={r}>
                      {r === "all" ? "All categories" : r === "top5" ? "Top 5" : "Bottom 5"}
                    </option>
                  ))}
                </select>
              </label>
            </>
          ) : null}
          <Button
            variant="outline"
            size="sm"
            disabled={busy || !packCat || (chartKind === "trend" && trendSeries.length === 0)}
            onClick={() =>
              void submit({
                decision: "edit",
                charts: [
                  chartKind === "trend"
                    ? ({ chart: "trend", series: trendSeries, weeks: trendWeeks } as ChartChoice)
                    : ({ chart: "variance", measure: varMeasure, rows: varRows } as ChartChoice),
                ],
              })
            }
          >
            <BarChart3 aria-hidden /> Change the chart
          </Button>
        </TabsContent>

        <TabsContent value="decide" className="mt-3 flex flex-col gap-2">
          <label htmlFor="comment" className="text-xs text-muted-foreground">
            Comment (needed to reject)
          </label>
          <textarea
            id="comment"
            dir="auto"
            rows={2}
            maxLength={500}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            className="w-full resize-y rounded-md border bg-background p-2 text-sm focus-visible:border-primary"
          />
          <Button
            size="lg"
            className="h-11"
            disabled={busy}
            onClick={() =>
              submit({ decision: "approve", ...(comment.trim() ? { comment: comment.trim() } : {}) })
            }
          >
            <ShieldCheck aria-hidden /> Approve the pack
          </Button>
          <Button
            variant="ghost"
            className="text-destructive hover:bg-alert-wash hover:text-destructive"
            disabled={busy || !comment.trim()}
            onClick={() => submit({ decision: "reject", comment: comment.trim() })}
          >
            <XCircle aria-hidden /> Reject
          </Button>
        </TabsContent>
      </Tabs>

      {graphRun && (busy || trace.length) ? <RunGraph trace={trace} running={busy} /> : null}
      {busy && !graphRun ? (
        <p className="flex items-center gap-2 text-xs text-muted-foreground" aria-live="polite">
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
          {trace.length ? `Working: ${trace.at(-1)}` : "Starting…"}
        </p>
      ) : null}
      {message ? (
        <p
          role={message.tone === "warn" ? "alert" : "status"}
          className={cn("text-sm", message.tone === "warn" ? "text-alert-ink" : "text-approved-ink")}
        >
          {message.text}
        </p>
      ) : null}
    </div>
  );
}
