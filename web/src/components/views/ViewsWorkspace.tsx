"use client";
// Charts (Frontend plan §6.5, ADR-066): ask in words (one model call chooses from the catalogue; no week → a question
// back) or choose from the catalogue (no model). Either way the API draws a ViewSpec from the finance views (= Power BI
// = the pack); the caption is code's; this page only draws and formats.
import { useQuery } from "@tanstack/react-query";
import { HelpCircle, Loader2, Sparkles } from "lucide-react";
import { useState } from "react";
import {
  catalogueApiV1ChartsCatalogueGet as getCatalogue,
  viewApiV1ViewsPost as postView,
  weeksApiV1FinanceWeeksGet as getWeeks,
  type RunAccepted,
  type ViewChoice,
  type ViewSpec,
} from "@/api/generated/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SeriesChart, SeriesTable } from "@/components/viz/SeriesChart";
import { BffError } from "@/lib/bff/client";
import { RunObservationError, streamRun } from "@/lib/runs";

type Named = Record<string, { name: string; unit: string }>;
type ViewsCatalogue = {
  kinds: string[];
  options: Record<string, string[]>;
  category: Named;
  customers: Named;
  aging: { field: string; name: string }[];
};
type TrendCatalogue = { series: Named; weeks: number[]; max_series: number };

const KIND_LABEL: Record<string, string> = {
  trend: "A trend over weeks",
  category: "Billing by vessel category",
  aging: "Receivables by age",
  customers: "Customers (13 weeks)",
};
const select = "h-9 w-full rounded-md border bg-background px-2 text-sm focus-visible:border-primary";

function problemText(error: unknown): string {
  if (error instanceof RunObservationError) return error.message;
  if (error instanceof BffError) {
    if (error.status === 403) return "This chart is Finance data, outside your access.";
    if (error.status === 404) return "There is no data for that week.";
    if (error.status === 429) return "Too many charts asked in the last hour. Try again later.";
    return error.title;
  }
  return "The chart could not be drawn. Try again.";
}

export function ViewResult({ spec }: { spec: ViewSpec }) {
  const kind = spec.choice.kind === "trend" ? "line" : "bar";
  const unit = spec.unit;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{spec.caption}</CardTitle>
        <CardDescription>Unit: {unit}</CardDescription>
      </CardHeader>
      <CardContent>
        <SeriesChart
          categories={spec.categories}
          series={spec.series}
          unit={unit}
          kind={kind}
          label={spec.caption}
        />
        <SeriesTable categories={spec.categories} series={spec.series} unit={unit} />
        {spec.sources?.length ? (
          <ul className="mt-3 flex flex-col gap-1 text-xs text-muted-foreground">
            {spec.sources.map((s, i) => (
              <li key={i} className="font-mono">
                {String((s as { view?: string; name?: string }).view ?? (s as { name?: string }).name ?? "")}{" "}
                — {String((s as { filter?: string }).filter ?? "")}
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function ViewsWorkspace() {
  const catalogue = useQuery({ queryKey: ["catalogue"], queryFn: () => getCatalogue() });
  const weeks = useQuery({ queryKey: ["finance-weeks"], queryFn: () => getWeeks() });
  const views = catalogue.data?.views as ViewsCatalogue | undefined;
  const trend = (catalogue.data?.pack as { trend?: TrendCatalogue } | undefined)?.trend;
  const lastWeek = weeks.data?.at(-1)?.report_week;

  const [question, setQuestion] = useState("");
  const [kind, setKind] = useState("trend");
  const [week, setWeek] = useState<number | null>(null);
  const [series, setSeries] = useState<string[]>(["billed_sdr", "budget_sdr"]);
  const [weekWindow, setWeekWindow] = useState(13);
  const [measure, setMeasure] = useState<string>("");
  const [rows, setRows] = useState("all");
  const [compare, setCompare] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [spec, setSpec] = useState<ViewSpec | null>(null);
  const [note, setNote] = useState<{ tone: "ask" | "warn"; text: string } | null>(null);

  const theWeek = week ?? lastWeek ?? null;
  const unitOf = (k: string) => trend?.series[k]?.unit;

  async function ask() {
    setBusy(true);
    setNote(null);
    try {
      const accepted = (await postView({ question: question.trim() })) as RunAccepted;
      await streamRun(accepted.run_id, {
        onEvent: (e) => {
          if (e.event === "answer") {
            const view = e.data.view as ViewSpec | null | undefined;
            if (view) setSpec(view);
            else if (e.data.status === "ask_back")
              setNote({ tone: "ask", text: String(e.data.answer ?? "Which week?") });
            else if (e.data.status === "not_permitted")
              setNote({ tone: "warn", text: problemText(new BffError(403, "", null)) });
            else setNote({ tone: "warn", text: "No chart could be chosen for that question. Try the form." });
          }
          if (e.event === "failed") setNote({ tone: "warn", text: e.data.detail });
        },
      });
    } catch (error) {
      setNote({ tone: "warn", text: problemText(error) });
    } finally {
      setBusy(false);
    }
  }

  async function choose() {
    if (theWeek === null) return;
    const choice: ViewChoice = { kind: kind as ViewChoice["kind"], week: theWeek };
    if (kind === "trend") Object.assign(choice, { series, weeks: weekWindow });
    if (kind === "category")
      Object.assign(choice, { measure: measure || "billed_sdr", rows, compare_week: compare });
    if (kind === "aging") Object.assign(choice, { compare_week: compare });
    if (kind === "customers") Object.assign(choice, { measure: measure || "share_13w_pct" });
    setBusy(true);
    setNote(null);
    try {
      setSpec((await postView({ choice })) as ViewSpec);
    } catch (error) {
      setNote({ tone: "warn", text: problemText(error) });
    } finally {
      setBusy(false);
    }
  }

  const measures =
    kind === "category" ? views?.category : kind === "customers" ? views?.customers : undefined;
  const firstUnit = series[0] ? unitOf(series[0]) : undefined;

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[22rem_minmax(0,1fr)]">
      <div className="flex flex-col gap-5">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Sparkles className="size-4 text-primary" aria-hidden /> Ask for a chart
            </CardTitle>
            <CardDescription>
              In English or Arabic. Name the week, or you will be asked for it.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            <label htmlFor="view-question" className="sr-only">
              Ask for a chart
            </label>
            <textarea
              id="view-question"
              dir="auto"
              rows={3}
              maxLength={300}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Billed vs budget % by category for week 23, top 5"
              className="w-full resize-y rounded-md border bg-background p-3 text-sm focus-visible:border-primary"
            />
            <Button disabled={busy || question.trim().length < 3} onClick={() => void ask()}>
              {busy ? <Loader2 className="animate-spin" aria-hidden /> : null} Draw it
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Or choose</CardTitle>
            <CardDescription>From the same catalogue the weekly pack uses.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-sm">
            <label className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Chart</span>
              <select className={select} value={kind} onChange={(e) => setKind(e.target.value)}>
                {(views?.kinds ?? ["trend"]).map((k) => (
                  <option key={k} value={k}>
                    {KIND_LABEL[k] ?? k}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Week of 2025</span>
              <select
                className={select}
                value={theWeek ?? ""}
                onChange={(e) => setWeek(Number(e.target.value))}
              >
                {(weeks.data ?? []).map((w) => (
                  <option key={w.report_week} value={w.report_week}>
                    {w.iso_week_label}
                  </option>
                ))}
              </select>
            </label>
            {kind === "trend" && trend ? (
              <>
                <fieldset className="flex flex-col gap-1">
                  <legend className="text-xs text-muted-foreground">
                    Series (up to {trend.max_series}, one unit)
                  </legend>
                  {Object.entries(trend.series).map(([k, s]) => {
                    const on = series.includes(k);
                    const blocked =
                      !on &&
                      (series.length >= trend.max_series ||
                        (firstUnit !== undefined && s.unit !== firstUnit));
                    return (
                      <label key={k} className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={on}
                          disabled={blocked}
                          onChange={() => setSeries((all) => (on ? all.filter((x) => x !== k) : [...all, k]))}
                        />
                        {s.name} <span className="text-xs text-muted-foreground">({s.unit})</span>
                      </label>
                    );
                  })}
                </fieldset>
                <label className="flex flex-col gap-1">
                  <span className="text-xs text-muted-foreground">Weeks shown</span>
                  <select
                    className={select}
                    value={weekWindow}
                    onChange={(e) => setWeekWindow(Number(e.target.value))}
                  >
                    {trend.weeks.map((w) => (
                      <option key={w} value={w}>
                        {w} weeks
                      </option>
                    ))}
                  </select>
                </label>
              </>
            ) : null}
            {measures ? (
              <label className="flex flex-col gap-1">
                <span className="text-xs text-muted-foreground">Measure</span>
                <select
                  className={select}
                  value={measure || Object.keys(measures)[0]}
                  onChange={(e) => setMeasure(e.target.value)}
                >
                  {Object.entries(measures).map(([k, m]) => (
                    <option key={k} value={k}>
                      {m.name} ({m.unit})
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {kind === "category" ? (
              <label className="flex flex-col gap-1">
                <span className="text-xs text-muted-foreground">Rows</span>
                <select className={select} value={rows} onChange={(e) => setRows(e.target.value)}>
                  <option value="all">All categories</option>
                  <option value="top5">Top 5</option>
                  <option value="bottom5">Bottom 5</option>
                </select>
              </label>
            ) : null}
            {kind === "category" || kind === "aging" ? (
              <label className="flex flex-col gap-1">
                <span className="text-xs text-muted-foreground">Compare with week</span>
                <select
                  className={select}
                  value={compare ?? ""}
                  onChange={(e) => setCompare(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">No comparison</option>
                  {(weeks.data ?? []).map((w) => (
                    <option key={w.report_week} value={w.report_week}>
                      {w.iso_week_label}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <Button
              variant="outline"
              disabled={busy || theWeek === null || (kind === "trend" && series.length === 0)}
              onClick={() => void choose()}
            >
              Draw the chart
            </Button>
          </CardContent>
        </Card>
      </div>

      <section aria-label="The chart" className="min-w-0">
        {note ? (
          <p
            role={note.tone === "warn" ? "alert" : "status"}
            className={
              note.tone === "warn"
                ? "mb-4 text-sm text-alert-ink"
                : "mb-4 flex items-center gap-2 text-sm text-waiting-ink"
            }
          >
            {note.tone === "ask" ? <HelpCircle className="size-4" aria-hidden /> : null}
            <span dir="auto">{note.text}</span>
          </p>
        ) : null}
        {busy && !spec ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Drawing…
          </p>
        ) : null}
        {spec ? (
          <ViewResult spec={spec} />
        ) : !busy ? (
          <p className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
            Ask in words or choose on the left. Every value comes from the finance views — the same numbers as
            Power BI and the weekly pack.
          </p>
        ) : null}
      </section>
    </div>
  );
}
