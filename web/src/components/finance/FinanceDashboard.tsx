"use client";
// The finance dashboard in the web (Frontend plan §6.9, D-FE-7 + D-FE-9): the Power BI pages drawn from the same
// `finance` views (GET /finance/*, the agents' own tools and RBAC), one week for every page, a two-line summary per
// page chosen by fixed code rules (which field moved most, which bucket is largest — a choice among the view's fields,
// never new arithmetic: ADR-047), every headline number a receipt, and this week's published pack.
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Download, Loader2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type ReactNode } from "react";
import {
  datasetApiV1FinanceDatasetGet as getDataset,
  invoiceAuditApiV1FinanceInvoiceAuditGet as getAudit,
  weekPackApiV1FinancePackGet as getWeekPack,
  weeksApiV1FinanceWeeksGet as getWeeks,
  type FinanceRows,
  type FinanceWeek,
} from "@/api/generated/client";
import { BreakdownCard } from "@/components/finance/Breakdown";
import { FigureCard, FigureDownload } from "@/components/finance/FigureCard";
import { NumberChip } from "@/components/receipt/NumberChip";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Sparkline } from "@/components/viz/charts";
import {
  AGING_TONES,
  BulletBars,
  Delta,
  DivergingCell,
  Meter,
  RankedBars,
  SegmentBar,
} from "@/components/viz/forms";
import { formatValue, SeriesChart, SeriesTable, type Unit } from "@/components/viz/SeriesChart";
import { PublicationSync } from "@/components/packs/PublicationSync";
import { BffError } from "@/lib/bff/client";

type Row = Record<string, unknown>;
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const PAGES = ["overview", "revenue", "receivables", "customers", "exceptions", "executive"] as const;
type Page = (typeof PAGES)[number];
const PAGE_LABEL: Record<Page, string> = {
  overview: "Overview",
  revenue: "Revenue",
  receivables: "Receivables",
  customers: "Customers",
  exceptions: "Exceptions",
  executive: "Executive",
};

/** A receipt for one field of one row of a dataset: the value as the view gave it, only formatted. */
function Figure({
  data,
  row,
  field,
  unit,
}: {
  data: FinanceRows | undefined;
  row: Row | undefined;
  field: string;
  unit: Unit;
}) {
  const v = num(row?.[field]);
  const text = formatValue(v, unit);
  if (v === null || !data?.source) return <span className="num">{text}</span>;
  return (
    <NumberChip
      span={{
        text: unit === "SDR" ? `${text} SDR` : text,
        start: 0,
        end: 0,
        evidence_id: `finance.${data.dataset}`,
        field,
        source: data.source.name,
        filter: data.source.filter,
        row: (data.rows ?? []).indexOf(row ?? {}),
      }}
    />
  );
}

/** A week-on-week change is good when it goes this way (a fixed rule per KPI, D-WD-5; none = not coloured). */
const GOOD_WHEN: Record<string, "up" | "down"> = {
  billed_wow_pct: "up",
  collected_wow_pct: "up",
  ar_wow_pct: "down",
  overdue_wow_pct: "down",
  dso_wow_days: "down",
};

function Kpi({
  label,
  data,
  row,
  field,
  unit,
  change,
  changeUnit = "%",
  trend,
}: {
  label: string;
  data: FinanceRows | undefined;
  row: Row | undefined;
  field: string;
  unit: Unit;
  change?: string;
  changeUnit?: Unit;
  /** the 13-week rows: when they hold this field, a sparkline (the view's values, the report week last) */
  trend?: Row[];
}) {
  const c = change ? num(row?.[change]) : null;
  const spark = (trend ?? []).map((t) => num(t[field])).filter((v): v is number => v !== null);
  return (
    <Card className="gap-2 py-4" data-kpi={field}>
      <CardHeader className="px-4">
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-xl tracking-tight">
          <Figure data={data} row={row} field={field} unit={unit} />
        </CardTitle>
      </CardHeader>
      {change || spark.length > 1 ? (
        <CardContent className="flex flex-col gap-2 px-4 text-xs">
          {change ? <Delta value={c} unit={changeUnit} goodWhen={GOOD_WHEN[change] ?? "up"} /> : null}
          {spark.length > 1 ? <Sparkline values={spark} className="h-7 w-32" /> : null}
        </CardContent>
      ) : null}
    </Card>
  );
}

/** The tiles of one page: a slim header with the source and the Download of exactly these figures. */
function KpiSection({
  week,
  page,
  data,
  children,
  className = "grid grid-cols-2 gap-4 lg:grid-cols-3",
}: {
  week: number;
  page: Page;
  data: FinanceRows;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section aria-label="Key figures" className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h2 className="text-sm font-medium">Key figures</h2>
        <span className="me-auto font-mono text-xs text-muted-foreground">
          {data.source?.name} — {data.source?.filter}
        </span>
        <FigureDownload name="Key figures" of={{ figure: "kpis", week, page }} />
      </div>
      <div className={className}>{children}</div>
    </section>
  );
}

function Summary({ lines }: { lines: string[] }) {
  return (
    <div className="rounded-xl border bg-accent/60 px-5 py-4 text-sm">
      {lines.map((l) => (
        <p key={l}>{l}</p>
      ))}
    </div>
  );
}

const pct = (v: number | null) => (v === null ? "—" : `${Math.abs(v).toFixed(1)}%`);
const signed = (v: number | null, unit: Unit) =>
  v === null ? "—" : `${v > 0 ? "+" : ""}${formatValue(v, unit)}${unit === "SDR" ? " SDR" : ""}`;

function useDataset(
  dataset: "weekly" | "category" | "customers" | "overdue" | "trend",
  week: number | null,
  limit?: number,
) {
  return useQuery({
    queryKey: ["finance", dataset, week, limit],
    queryFn: () => getDataset(dataset, { week: week as number, ...(limit ? { limit } : {}) }),
    enabled: week !== null,
  });
}

/** The 13-week rows (shared by the trend cards and the tiles' sparklines: one request per week). */
function useTrend(week: number) {
  return (useDataset("trend", week).data?.rows ?? []) as Row[];
}

function Loading({ error }: { error: unknown }) {
  if (error)
    return (
      <p role="alert" className="text-sm text-alert-ink">
        {error instanceof BffError && error.status === 403
          ? "This is Finance data, outside your access."
          : "This page could not be loaded."}
      </p>
    );
  return <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden />;
}

const MONEY_TREND: [string, string][] = [
  ["Billed", "billed_sdr"],
  ["Budget", "budget_sdr"],
  ["Collected", "collected_sdr"],
];

/** 13 weeks: billed as bars (the report week in colour, the others muted) with budget and collected as lines, or one
 * measure as an area; the report week is the view's `is_report_week` row. */
function TrendCard({
  week,
  title,
  fields = MONEY_TREND,
  unit = "SDR",
  kind = "combo",
}: {
  week: number;
  title: string;
  fields?: [string, string][];
  unit?: Unit;
  kind?: "combo" | "area";
}) {
  const trend = useDataset("trend", week);
  const rows = (trend.data?.rows ?? []) as Row[];
  if (!trend.data) return <Loading error={trend.error} />;
  const cats = rows.map((r) => String(r.trend_week_label ?? r.trend_week));
  const series = fields.map(([name, f]) => ({ name, values: rows.map((r) => num(r[f])) }));
  const marked = rows.findIndex((r) => r.is_report_week === true);
  const highlight = marked >= 0 ? marked : rows.length - 1;
  return (
    <FigureCard
      title={title}
      source={`${trend.data.source?.name} — ${trend.data.source?.filter}`}
      of={{ figure: "trend", week }}
    >
      <SeriesChart
        categories={cats}
        series={series}
        unit={unit}
        kind={kind}
        label={title}
        highlight={highlight}
      />
      <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
        <span className="inline-block h-3 w-[3px] rounded-full bg-marker" aria-hidden />
        {cats[highlight] ?? ""} is the report week{kind === "combo" ? "; earlier weeks are muted" : ""}.
      </p>
      <SeriesTable categories={cats} series={series} unit={unit} />
    </FigureCard>
  );
}

function Overview({ week }: { week: number }) {
  const weekly = useDataset("weekly", week);
  const trend = useTrend(week);
  const r = weekly.data?.rows?.[0] as Row | undefined;
  if (!weekly.data) return <Loading error={weekly.error} />;
  if (!r) return <p className="text-sm text-muted-foreground">No data for this week.</p>;
  const moves = (
    [
      ["Billing", "billed_wow_pct"],
      ["Collections", "collected_wow_pct"],
      ["Receivables", "ar_wow_pct"],
      ["Overdue", "overdue_wow_pct"],
    ] as const
  )
    .map(([label, f]): [string, number | null] => [label, num(r[f])])
    .filter((m): m is [string, number] => m[1] !== null)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const bv = num(r.budget_variance_pct);
  const lines = [
    bv === null
      ? "No budget for this week."
      : `Billing was ${pct(bv)} ${bv >= 0 ? "above" : "below"} the week's budget.`,
    moves[0]
      ? `The largest move on last week: ${moves[0][0].toLowerCase()} ${moves[0][1] >= 0 ? "up" : "down"} ${pct(moves[0][1])}.`
      : "",
  ].filter(Boolean);
  return (
    <div className="flex flex-col gap-5">
      <Summary lines={lines} />
      <KpiSection week={week} page="overview" data={weekly.data}>
        <Kpi
          label="Billed"
          data={weekly.data}
          row={r}
          field="billed_sdr"
          unit="SDR"
          change="billed_wow_pct"
          trend={trend}
        />
        <Kpi
          label="Collected"
          data={weekly.data}
          row={r}
          field="collected_sdr"
          unit="SDR"
          change="collected_wow_pct"
          trend={trend}
        />
        <Kpi
          label="Receivables"
          data={weekly.data}
          row={r}
          field="ar_sdr"
          unit="SDR"
          change="ar_wow_pct"
          trend={trend}
        />
        <Kpi
          label="Overdue"
          data={weekly.data}
          row={r}
          field="overdue_sdr"
          unit="SDR"
          change="overdue_wow_pct"
          trend={trend}
        />
        <Kpi
          label="DSO"
          data={weekly.data}
          row={r}
          field="dso_days"
          unit="days"
          change="dso_wow_days"
          changeUnit="days"
          trend={trend}
        />
        <Kpi
          label="Invoices billed"
          data={weekly.data}
          row={r}
          field="invoices_billed"
          unit={null}
          trend={trend}
        />
      </KpiSection>
      {r.is_warmup && weekly.data.note ? (
        <p className="flex gap-2 rounded-lg border px-4 py-3 text-sm text-muted-foreground">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden /> {weekly.data.note}
        </p>
      ) : null}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <FigureCard
          title="Billed against budget"
          source={`${weekly.data.source?.name} — ${weekly.data.source?.filter}`}
          of={{ figure: "kpis", week, page: "overview" }}
        >
          <BulletBars
            label="Billed against budget"
            unit="SDR"
            rows={[
              {
                label: String(r.iso_week_label ?? `W${week}`),
                value: num(r.billed_sdr),
                target: num(r.budget_sdr),
                note: `${signed(bv, "%")} vs budget`,
              },
            ]}
          />
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5 text-sm">
              <span className="text-muted-foreground">Billed vs budget, 13 weeks</span>
              <Delta value={num(r.budget_variance_13w_pct)} unit="%" goodWhen="up" suffix="vs budget" />
            </div>
            <Meter label="Top 10 customers, share of 13 weeks" value={num(r.top10_share_13w_pct)} />
          </div>
        </FigureCard>
        <TrendCard week={week} title="Billed, budget and collected — 13 weeks" />
      </div>
    </div>
  );
}

function Revenue({ week, weeks }: { week: number; weeks: FinanceWeek[] }) {
  const cat = useDataset("category", week);
  const weekly = useDataset("weekly", week);
  const trend = useTrend(week);
  const w = weekly.data?.rows?.[0] as Row | undefined;
  if (!cat.data) return <Loading error={cat.error} />;
  const rows = (cat.data.rows ?? []) as Row[];
  const top = rows[0];
  const cats = rows.map((r) => String(r.vessel_category));
  const series = [
    { name: "Billed", values: rows.map((r) => num(r.billed_sdr)) },
    { name: "Budget", values: rows.map((r) => num(r.budget_sdr)) },
  ];
  const change = num(top?.billed_wow_change_sdr);
  const below = rows.filter((r) => (num(r.budget_variance_sdr) ?? 0) < 0);
  return (
    <div className="flex flex-col gap-5">
      <Summary
        lines={[
          top && change !== null
            ? `The biggest driver this week: ${String(top.vessel_category)}, ${change >= 0 ? "up" : "down"} ${formatValue(Math.abs(change), "SDR")} SDR on last week.`
            : "No category moved this week.",
          `${below.length} of ${rows.length} categories billed below budget.`,
        ]}
      />
      {weekly.data ? (
        <KpiSection week={week} page="revenue" data={weekly.data}>
          <Kpi
            label="Invoices billed"
            data={weekly.data}
            row={w}
            field="invoices_billed"
            unit={null}
            trend={trend}
          />
          <Kpi
            label="Billed"
            data={weekly.data}
            row={w}
            field="billed_sdr"
            unit="SDR"
            change="billed_wow_pct"
            trend={trend}
          />
          <Kpi
            label="Billed vs budget"
            data={weekly.data}
            row={w}
            field="budget_variance_pct"
            unit="%"
            trend={trend}
          />
        </KpiSection>
      ) : null}
      <FigureCard
        title="Billing against budget by vessel category"
        source={`${cat.data.source?.name} — ${cat.data.source?.filter}`}
        of={{ figure: "category", week }}
      >
        <BulletBars
          label="Billing against budget by vessel category"
          unit="SDR"
          rows={rows.map((r) => ({
            label: String(r.vessel_category),
            value: num(r.billed_sdr),
            target: num(r.budget_sdr),
            note: `${signed(num(r.budget_variance_sdr), "SDR")}`,
          }))}
        />
        <SeriesTable categories={cats} series={series} unit="SDR" />
      </FigureCard>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <BreakdownCard id="rev1" week={week} weeks={weeks} title="Revenue by toll band" initial="toll_band" />
        <BreakdownCard id="rev2" week={week} weeks={weeks} title="Top routes by revenue" initial="route" />
        <BreakdownCard
          id="rev3"
          week={week}
          weeks={weeks}
          title="Laden vs ballast"
          initial="priced_condition"
        />
        <BreakdownCard
          id="rev4"
          week={week}
          weeks={weeks}
          title="Revenue by customer segment"
          initial="customer_segment"
        />
      </div>
      <TrendCard
        week={week}
        title="Billed against budget — 13 weeks"
        fields={[
          ["Billed", "billed_sdr"],
          ["Budget", "budget_sdr"],
        ]}
      />
    </div>
  );
}

const AGING: [string, string][] = [
  ["aging_current_sdr", "Current"],
  ["aging_1_30_sdr", "1–30 days"],
  ["aging_31_60_sdr", "31–60 days"],
  ["aging_61_90_sdr", "61–90 days"],
  ["aging_90_plus_sdr", "90+ days"],
];

function Receivables({ week }: { week: number }) {
  const weekly = useDataset("weekly", week);
  const overdue = useDataset("overdue", week, 50);
  const trend = useTrend(week);
  const r = weekly.data?.rows?.[0] as Row | undefined;
  if (!weekly.data || !overdue.data) return <Loading error={weekly.error ?? overdue.error} />;
  const buckets = AGING.map(([f, label]) => [label, num(r?.[f])] as const);
  const largest = [...buckets].filter((b) => b[1] !== null).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))[0];
  const src = `${weekly.data.source?.name} — ${weekly.data.source?.filter}`;
  const series = [{ name: "Receivables", values: buckets.map((b) => b[1]) }];
  const dueCollected = num(r?.due_week_collected_pct);
  return (
    <div className="flex flex-col gap-5">
      <Summary
        lines={[
          largest
            ? `The largest part of receivables is ${largest[0].toLowerCase()}.`
            : "No receivables this week.",
          `${(overdue.data.rows ?? []).length} overdue invoices listed, largest first.`,
        ]}
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <FigureCard
          title="Receivables by age"
          source={src}
          of={{ figure: "kpis", week, page: "receivables" }}
        >
          <SegmentBar
            label="Receivables by age"
            unit="SDR"
            parts={buckets.map(([label, v], i) => ({ label, value: v, className: AGING_TONES[i] }))}
          />
          <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className="inline-block size-2.5 rounded-[3px] bg-marker" aria-hidden /> 90+ days is the
            oldest debt; the blues darken with age.
          </p>
          <SeriesTable categories={buckets.map((b) => b[0])} series={series} unit="SDR" />
        </FigureCard>
        <FigureCard title="DSO and its parts" source={src} of={{ figure: "kpis", week, page: "receivables" }}>
          <SegmentBar
            label="DSO split into payment terms and late payment"
            unit="days"
            thin
            total={{ label: "DSO", text: formatValue(num(r?.dso_days), "days") }}
            parts={[
              { label: "DSO at best (payment terms)", value: num(r?.dso_best_days), className: "bg-chart-1" },
              { label: "DSO from late payment", value: num(r?.dso_delinquency_days), className: "bg-alert" },
            ]}
          />
          <div className="mt-5">
            <Meter
              label="Due this week, collected"
              value={dueCollected}
              alertBelow={50}
              detail="Of the invoices due this week."
            />
          </div>
        </FigureCard>
      </div>
      <KpiSection
        week={week}
        page="receivables"
        data={weekly.data}
        className="grid grid-cols-2 gap-4 lg:grid-cols-3"
      >
        <Kpi
          label="Receivables"
          data={weekly.data}
          row={r}
          field="ar_sdr"
          unit="SDR"
          change="ar_wow_pct"
          trend={trend}
        />
        <Kpi
          label="Collected"
          data={weekly.data}
          row={r}
          field="collected_sdr"
          unit="SDR"
          change="collected_wow_pct"
          trend={trend}
        />
        <Kpi
          label="Overdue"
          data={weekly.data}
          row={r}
          field="overdue_sdr"
          unit="SDR"
          change="overdue_wow_pct"
          trend={trend}
        />
        <Kpi
          label="DSO"
          data={weekly.data}
          row={r}
          field="dso_days"
          unit="days"
          change="dso_wow_days"
          changeUnit="days"
          trend={trend}
        />
        <Kpi label="Newly overdue" data={weekly.data} row={r} field="overdue_new_sdr" unit="SDR" />
        <Kpi label="Overdue paid" data={weekly.data} row={r} field="overdue_paid_sdr" unit="SDR" />
      </KpiSection>
      <TrendCard week={week} title="DSO — 13 weeks" fields={[["DSO", "dso_days"]]} unit="days" kind="area" />
      <FigureCard
        title="Overdue invoices"
        source={overdue.data.source?.name}
        of={{ figure: "overdue", week, limit: 50 }}
      >
        <div className="overflow-x-auto" role="region" aria-label="Overdue invoices table" tabIndex={0}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-xs text-muted-foreground">
                <th className="py-2 pe-3 text-start font-medium">Invoice</th>
                <th className="py-2 pe-3 text-start font-medium">Customer</th>
                <th className="py-2 pe-3 text-start font-medium">Vessel</th>
                <th className="py-2 pe-3 text-start font-medium">Due date</th>
                <th className="py-2 pe-3 text-end font-medium">Amount (SDR)</th>
                <th className="py-2 pe-3 text-end font-medium">Days past due</th>
                <th className="py-2 pe-3 text-start font-medium">Age</th>
              </tr>
            </thead>
            <tbody>
              {((overdue.data.rows ?? []) as Row[]).slice(0, 15).map((o) => {
                const oldest =
                  /90/.test(String(o.aging_bucket ?? "")) && /\+|plus/.test(String(o.aging_bucket));
                return (
                  <tr key={String(o.invoice_number)} className="border-b last:border-0">
                    <td className="py-2 pe-3 font-mono text-xs">{String(o.invoice_number)}</td>
                    <td className="py-2 pe-3">{String(o.customer_name ?? "")}</td>
                    <td className="py-2 pe-3">{String(o.vessel_name ?? "")}</td>
                    <td className="py-2 pe-3 font-mono text-xs">{String(o.due_date ?? "")}</td>
                    <td className="num py-2 pe-3 text-end">{formatValue(num(o.amount_sdr), "SDR")}</td>
                    <td className="num py-2 pe-3 text-end">{String(o.days_past_due ?? "")}</td>
                    <td className="py-2 pe-3">
                      {oldest ? (
                        <span className="rounded-full bg-alert-wash px-2 py-0.5 text-xs text-alert-ink">
                          {String(o.aging_bucket)}
                        </span>
                      ) : (
                        String(o.aging_bucket ?? "")
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </FigureCard>
    </div>
  );
}

function Customers({ week, weeks }: { week: number; weeks: FinanceWeek[] }) {
  const cust = useDataset("customers", week, 20);
  const weekly = useDataset("weekly", week);
  const w = weekly.data?.rows?.[0] as Row | undefined;
  if (!cust.data) return <Loading error={cust.error} />;
  const rows = (cust.data.rows ?? []) as Row[];
  const top10 = rows.slice(0, 10);
  const watch = rows.filter((r) => r.is_watchlist === true).length;
  return (
    <div className="flex flex-col gap-5">
      <Summary
        lines={[
          rows[0]
            ? `The largest customer over 13 weeks: ${String(rows[0].customer_name)}, ${pct(num(rows[0].share_13w_pct))} of billing.`
            : "No customer data.",
          `${watch} of the top ${rows.length} customers are on the watchlist.`,
        ]}
      />
      {weekly.data ? (
        <KpiSection week={week} page="customers" data={weekly.data}>
          <Kpi label="Billed, 13 weeks" data={weekly.data} row={w} field="billed_13w_sdr" unit="SDR" />
          <Kpi
            label="Top 10 customers, share"
            data={weekly.data}
            row={w}
            field="top10_share_13w_pct"
            unit="%"
          />
          <Kpi label="Paid on time, 13 weeks" data={weekly.data} row={w} field="ontime_13w_pct" unit="%" />
        </KpiSection>
      ) : null}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <FigureCard
          title="Top 10 customers — billed in the last 13 weeks"
          source={cust.data.source?.name}
          of={{ figure: "customers", week, limit: 20 }}
        >
          <RankedBars
            label="Top 10 customers — billed in the last 13 weeks"
            unit="SDR"
            seriesName="Billed, 13 weeks"
            rows={top10.map((c) => ({
              label: String(c.customer_name ?? ""),
              value: num(c.billed_13w_sdr),
              flag: c.is_watchlist ? "watch" : undefined,
            }))}
          />
          {watch ? (
            <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="inline-block size-2.5 rounded-[3px] bg-alert" aria-hidden /> On the watchlist.
            </p>
          ) : null}
        </FigureCard>
        <BreakdownCard
          id="cus1"
          week={week}
          weeks={weeks}
          title="This week's billing by customer group"
          initial="customer_segment"
        />
      </div>
      <FigureCard
        title="Customers — trailing 13 weeks"
        source={`${cust.data.source?.name} — ${cust.data.source?.filter}`}
        of={{ figure: "customers", week, limit: 20 }}
        label="Customers table — trailing 13 weeks"
      >
        <div className="overflow-x-auto" role="region" aria-label="Customers table" tabIndex={0}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-xs text-muted-foreground">
                <th className="py-2 pe-3 text-start font-medium">#</th>
                <th className="py-2 pe-3 text-start font-medium">Customer</th>
                <th className="py-2 pe-3 text-end font-medium">Share</th>
                <th className="py-2 pe-3 text-start font-medium">Rating</th>
                <th className="py-2 pe-3 text-end font-medium">Terms (days)</th>
                <th className="py-2 pe-3 text-end font-medium">Receivables</th>
                <th className="py-2 pe-3 text-end font-medium">Overdue</th>
                <th className="py-2 pe-3 text-end font-medium">Receivables / billed</th>
                <th className="py-2 pe-3 text-end font-medium">On time</th>
                <th className="py-2 pe-3 text-start font-medium">Watchlist</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr
                  key={String(c.customer_id)}
                  className={`border-b last:border-0 ${c.is_watchlist ? "bg-alert-wash/40" : ""}`}
                >
                  <td className="num py-2 pe-3">{String(c.rank_13w ?? "")}</td>
                  <td className="py-2 pe-3">{String(c.customer_name ?? "")}</td>
                  <td className="num py-2 pe-3 text-end">{formatValue(num(c.share_13w_pct), "%")}</td>
                  <td className="py-2 pe-3">{String(c.credit_rating ?? "")}</td>
                  <td className="num py-2 pe-3 text-end">{String(c.payment_terms_days ?? "")}</td>
                  <td className="num py-2 pe-3 text-end">{formatValue(num(c.ar_sdr), "SDR")}</td>
                  <td className="num py-2 pe-3 text-end">{formatValue(num(c.overdue_sdr), "SDR")}</td>
                  <td className="num py-2 pe-3 text-end">{formatValue(num(c.ar_to_billed_13w_pct), "%")}</td>
                  <td className="num py-2 pe-3 text-end">{formatValue(num(c.ontime_13w_pct), "%")}</td>
                  <td className="py-2 pe-3">
                    {c.is_watchlist ? (
                      <span className="rounded-full bg-alert-wash px-2 py-0.5 text-xs text-alert-ink">
                        watch
                      </span>
                    ) : (
                      ""
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </FigureCard>
    </div>
  );
}

const PERIODS: [boolean, string][] = [
  [false, "This week"],
  [true, "Year to date"],
];

function Exceptions({ week }: { week: number }) {
  const [ytd, setYtd] = useState(false);
  const audit = useQuery({
    queryKey: ["finance", "audit", week, ytd],
    queryFn: () => getAudit({ week, ...(ytd ? { ytd: true } : {}) }),
  });
  if (!audit.data) return <Loading error={audit.error} />;
  const a = audit.data;
  const found = ((a.rows ?? []) as Row[]).slice(0, ytd ? 100 : 20);
  const maxDiff = Math.max(0, ...found.map((f) => Math.abs(num(f.difference_sdr) ?? 0)));
  const src = `${a.source?.name} — ${a.source?.filter}`;
  const period = (
    <div role="group" aria-label="Findings period" className="mt-2 flex gap-1">
      {PERIODS.map(([v, label]) => (
        <button
          key={label}
          type="button"
          aria-pressed={ytd === v}
          onClick={() => setYtd(v)}
          className={`h-7 rounded-md px-2.5 text-xs ${ytd === v ? "bg-primary text-primary-foreground" : "border"}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
  return (
    <div className="flex flex-col gap-5">
      <Summary
        lines={[
          `${a.invoices_flagged ?? 0} of ${a.invoices_checked ?? 0} invoices ${ytd ? "of the year to date" : "of the week"} have a finding.`,
          a.invoices_manual_review
            ? `${a.invoices_manual_review} need a person's review (a tariff Notes rule may apply).`
            : "No invoice waits for a manual review.",
        ]}
      />
      <FigureCard
        title="Audit summary"
        source={src}
        of={{ figure: "audit_summary", week, ytd }}
        controls={period}
      >
        <div className="grid grid-cols-1 gap-5 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          <Meter
            label="Invoices with a finding"
            value={null}
            of={{
              part: a.invoices_flagged ?? 0,
              whole: a.invoices_checked ?? 0,
              ...(a.invoices_flagged ? { tone: "alert" as const } : {}),
            }}
            detail={ytd ? "Year to date." : "This week."}
          />
          <dl className="grid grid-cols-3 gap-3 text-sm">
            <div>
              <dt className="text-xs text-muted-foreground">Checked</dt>
              <dd className="num text-xl font-semibold">{a.invoices_checked ?? 0}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Amount at stake</dt>
              <dd className="num text-xl font-semibold">
                {formatValue(a.amount_at_stake_sdr ?? null, "SDR")} SDR
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Manual review</dt>
              <dd
                className={`num text-xl font-semibold ${a.invoices_manual_review ? "text-waiting-ink" : ""}`}
              >
                {a.invoices_manual_review ?? 0}
              </dd>
            </div>
          </dl>
        </div>
      </FigureCard>
      <FigureCard title="Findings" source={src} of={{ figure: "audit_findings", week, ytd }}>
        <div className="overflow-x-auto" role="region" aria-label="Findings table" tabIndex={0}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-xs text-muted-foreground">
                <th className="py-2 pe-3 text-start font-medium">Invoice</th>
                <th className="py-2 pe-3 text-start font-medium">Date</th>
                <th className="py-2 pe-3 text-start font-medium">Check</th>
                <th className="py-2 pe-3 text-start font-medium">Probable cause</th>
                <th className="py-2 pe-3 text-end font-medium">Billed (SDR)</th>
                <th className="py-2 pe-3 text-end font-medium">Expected (SDR)</th>
                <th className="py-2 pe-3 text-end font-medium">Difference (SDR)</th>
                <th className="py-2 pe-3 text-start font-medium">Duplicate of</th>
              </tr>
            </thead>
            <tbody>
              {found.map((f, i) => (
                <tr key={`${String(f.invoice_number)}-${i}`} className="border-b last:border-0">
                  <td className="py-2 pe-3 font-mono text-xs">
                    {String(f.invoice_number)}
                    {f.review === "manual_review" ? (
                      <span className="ms-2 rounded-full bg-waiting-wash px-1.5 py-px font-sans text-[11px] text-waiting-ink">
                        manual review
                      </span>
                    ) : null}
                  </td>
                  <td className="py-2 pe-3 font-mono text-xs">{String(f.invoice_date ?? "")}</td>
                  <td className="py-2 pe-3 font-mono text-xs">{String(f.check_code ?? "")}</td>
                  <td className="py-2 pe-3">{String(f.probable_cause ?? "")}</td>
                  <td className="num py-2 pe-3 text-end">{formatValue(num(f.billed_sdr), "SDR")}</td>
                  <td className="num py-2 pe-3 text-end">{formatValue(num(f.expected_sdr), "SDR")}</td>
                  <td className="py-2 pe-3 text-end">
                    <DivergingCell value={num(f.difference_sdr)} max={maxDiff} unit="SDR" />
                  </td>
                  <td className="py-2 pe-3 font-mono text-xs">{String(f.duplicate_of ?? "")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {found.length === 0 ? (
          <p className="py-3 text-sm text-muted-foreground">No finding this week.</p>
        ) : (
          <p className="mt-2 text-xs text-muted-foreground">
            The difference bar points right (orange) when billed is above expected, left (blue) when below.
          </p>
        )}
      </FigureCard>
    </div>
  );
}

function WeekPack({ week }: { week: number }) {
  const pack = useQuery({
    queryKey: ["finance", "pack", week],
    queryFn: () => getWeekPack({ week }),
    retry: false,
  });
  return (
    <Card aria-label="This week's pack">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <CheckCircle2 className="size-4 text-approved" aria-hidden /> This week&apos;s pack
        </CardTitle>
        <CardDescription>
          {pack.data
            ? `Approved ${pack.data.approved_at ? new Date(pack.data.approved_at).toLocaleString("en-GB", { timeZone: "Africa/Cairo" }) : ""} by employee ${pack.data.approver_employee_id ?? "—"}.`
            : "The published weekly pack, when there is one."}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {pack.isPending ? (
          <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden />
        ) : null}
        {pack.error ? (
          <p className="text-sm text-muted-foreground">No pack has been published for this week yet.</p>
        ) : null}
        {pack.data ? (
          <>
            <PublicationSync status={pack.data.publication_sync} />
            {pack.data.degraded ? (
              <p className="flex gap-2 text-xs text-muted-foreground">
                <AlertTriangle className="size-3.5" aria-hidden /> Some texts were written by code.
              </p>
            ) : null}
            <ul className="flex flex-col gap-1.5 text-sm">
              {pack.data.summary.map((s) => (
                <li key={s} dir="auto" className="border-s-2 border-chart-1 ps-3">
                  {s}
                </li>
              ))}
            </ul>
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              {pack.data.charts.map((c) => (
                <div key={c.caption}>
                  <p className="mb-1 text-xs font-medium">{c.caption}</p>
                  <SeriesChart
                    categories={c.categories}
                    series={c.series}
                    unit={c.unit}
                    kind={c.choice.kind === "trend" ? "line" : "bar"}
                    label={c.caption}
                    height={220}
                  />
                </div>
              ))}
            </div>
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Executive({ week }: { week: number }) {
  const weekly = useDataset("weekly", week);
  const trend = useTrend(week);
  const r = weekly.data?.rows?.[0] as Row | undefined;
  if (!weekly.data) return <Loading error={weekly.error} />;
  const b13 = num(r?.budget_variance_13w_pct);
  return (
    <div className="flex flex-col gap-5">
      <Summary
        lines={[
          b13 === null
            ? "No 13-week budget position."
            : `Over 13 weeks, billing is ${pct(b13)} ${b13 >= 0 ? "above" : "below"} budget.`,
          `On-time payment over 13 weeks: ${pct(num(r?.ontime_13w_pct))}.`,
        ]}
      />
      <KpiSection
        week={week}
        page="executive"
        data={weekly.data}
        className="grid grid-cols-2 gap-4 lg:grid-cols-4"
      >
        <Kpi
          label="Billed this week"
          data={weekly.data}
          row={r}
          field="billed_sdr"
          unit="SDR"
          change="billed_wow_pct"
          trend={trend}
        />
        <Kpi label="Billed, 13 weeks" data={weekly.data} row={r} field="billed_13w_sdr" unit="SDR" />
        <Kpi
          label="Overdue"
          data={weekly.data}
          row={r}
          field="overdue_sdr"
          unit="SDR"
          change="overdue_wow_pct"
          trend={trend}
        />
        <Kpi label="DSO" data={weekly.data} row={r} field="dso_days" unit="days" trend={trend} />
      </KpiSection>
      <WeekPack week={week} />
    </div>
  );
}

export function FinanceDashboard() {
  const router = useRouter();
  const params = useSearchParams();
  const weeks = useQuery({ queryKey: ["finance-weeks"], queryFn: () => getWeeks() });
  const requested = Number(params.get("week"));
  const all = weeks.data ?? [];
  const week = all.some((w) => w.report_week === requested) ? requested : (all.at(-1)?.report_week ?? null);
  const page = (PAGES as readonly string[]).includes(params.get("page") ?? "")
    ? (params.get("page") as Page)
    : "overview";
  const go = (next: { week?: number; page?: Page }) => {
    const q = new URLSearchParams({ week: String(next.week ?? week ?? ""), page: next.page ?? page });
    router.replace(`/finance?${q.toString()}`, { scroll: false });
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end gap-4">
        <div className="me-auto">
          <h1 className="text-2xl font-semibold">Dashboards</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            The same views as Power BI and the weekly pack. Hover a number for its source; every card
            downloads its own numbers.
          </p>
        </div>
        {week !== null ? (
          <a
            href={`/bff/finance/export?${new URLSearchParams({ week: String(week), page }).toString()}`}
            download
            className="inline-flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-medium text-primary hover:bg-accent"
          >
            <Download className="size-4" aria-hidden /> Export whole page
          </a>
        ) : null}
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs text-muted-foreground">Week of 2025</span>
          <select
            className="h-9 rounded-md border bg-background px-2"
            value={week ?? ""}
            onChange={(e) => go({ week: Number(e.target.value) })}
          >
            {all.map((w) => (
              <option key={w.report_week} value={w.report_week}>
                {w.iso_week_label}
                {w.is_warmup ? " (warm-up)" : ""}
              </option>
            ))}
          </select>
        </label>
      </div>
      {weeks.error ? <Loading error={weeks.error} /> : null}
      {week === null ? (
        weeks.isPending ? (
          <Loading error={null} />
        ) : null
      ) : (
        <Tabs value={page} onValueChange={(v) => go({ page: v as Page })}>
          <TabsList className="flex-wrap group-data-horizontal/tabs:h-auto">
            {PAGES.map((p) => (
              <TabsTrigger key={p} value={p} className="h-7">
                {PAGE_LABEL[p]}
              </TabsTrigger>
            ))}
          </TabsList>
          <TabsContent value="overview" className="mt-5">
            <Overview week={week} />
          </TabsContent>
          <TabsContent value="revenue" className="mt-5">
            <Revenue week={week} weeks={all} />
          </TabsContent>
          <TabsContent value="receivables" className="mt-5">
            <Receivables week={week} />
          </TabsContent>
          <TabsContent value="customers" className="mt-5">
            <Customers week={week} weeks={all} />
          </TabsContent>
          <TabsContent value="exceptions" className="mt-5">
            <Exceptions week={week} />
          </TabsContent>
          <TabsContent value="executive" className="mt-5">
            <Executive week={week} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
