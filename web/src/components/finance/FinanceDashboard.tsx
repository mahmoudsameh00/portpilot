"use client";
// The finance dashboard in the web (Frontend plan §6.9, D-FE-7 + D-FE-9): the Power BI pages drawn from the same
// `finance` views (GET /finance/*, the agents' own tools and RBAC), one week for every page, a two-line summary per
// page chosen by fixed code rules (which field moved most, which bucket is largest — a choice among the view's fields,
// never new arithmetic: ADR-047), every headline number a receipt, and this week's published pack.
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  datasetApiV1FinanceDatasetGet as getDataset,
  invoiceAuditApiV1FinanceInvoiceAuditGet as getAudit,
  weekPackApiV1FinancePackGet as getWeekPack,
  weeksApiV1FinanceWeeksGet as getWeeks,
  type FinanceRows,
} from "@/api/generated/client";
import { NumberChip } from "@/components/receipt/NumberChip";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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

function Kpi({
  label,
  data,
  row,
  field,
  unit,
  change,
  changeUnit = "%",
}: {
  label: string;
  data: FinanceRows | undefined;
  row: Row | undefined;
  field: string;
  unit: Unit;
  change?: string;
  changeUnit?: Unit;
}) {
  const c = change ? num(row?.[change]) : null;
  return (
    <Card className="gap-2 py-4">
      <CardHeader className="px-4">
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-xl tracking-tight">
          <Figure data={data} row={row} field={field} unit={unit} />
        </CardTitle>
      </CardHeader>
      {change ? (
        <CardContent className="px-4 text-xs text-muted-foreground">
          {c === null ? "no change data" : `${c > 0 ? "+" : ""}${formatValue(c, changeUnit)} on last week`}
        </CardContent>
      ) : null}
    </Card>
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

function TrendCard({ week, title }: { week: number; title: string }) {
  const trend = useDataset("trend", week);
  const rows = (trend.data?.rows ?? []) as Row[];
  if (!trend.data) return <Loading error={trend.error} />;
  const cats = rows.map((r) => String(r.trend_week_label ?? r.trend_week));
  const series = [
    { name: "Billed", values: rows.map((r) => num(r.billed_sdr)) },
    { name: "Budget", values: rows.map((r) => num(r.budget_sdr)) },
    { name: "Collected", values: rows.map((r) => num(r.collected_sdr)) },
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription className="font-mono text-xs">
          {trend.data.source?.name} — {trend.data.source?.filter}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <SeriesChart categories={cats} series={series} unit="SDR" kind="line" label={title} />
        <SeriesTable categories={cats} series={series} unit="SDR" />
      </CardContent>
    </Card>
  );
}

function Overview({ week }: { week: number }) {
  const weekly = useDataset("weekly", week);
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
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <Kpi
          label="Billed"
          data={weekly.data}
          row={r}
          field="billed_sdr"
          unit="SDR"
          change="billed_wow_pct"
        />
        <Kpi
          label="Collected"
          data={weekly.data}
          row={r}
          field="collected_sdr"
          unit="SDR"
          change="collected_wow_pct"
        />
        <Kpi label="Receivables" data={weekly.data} row={r} field="ar_sdr" unit="SDR" change="ar_wow_pct" />
        <Kpi
          label="Overdue"
          data={weekly.data}
          row={r}
          field="overdue_sdr"
          unit="SDR"
          change="overdue_wow_pct"
        />
        <Kpi
          label="DSO"
          data={weekly.data}
          row={r}
          field="dso_days"
          unit="days"
          change="dso_wow_days"
          changeUnit="days"
        />
        <Kpi label="Billed vs budget" data={weekly.data} row={r} field="budget_variance_pct" unit="%" />
      </div>
      <TrendCard week={week} title="Billed, budget and collected — 13 weeks" />
    </div>
  );
}

function Revenue({ week }: { week: number }) {
  const cat = useDataset("category", week);
  if (!cat.data) return <Loading error={cat.error} />;
  const rows = (cat.data.rows ?? []) as Row[];
  const top = rows[0];
  const cats = rows.map((r) => String(r.vessel_category));
  const series = [
    { name: "Billed", values: rows.map((r) => num(r.billed_sdr)) },
    { name: "Budget", values: rows.map((r) => num(r.budget_sdr)) },
  ];
  const change = num(top?.billed_wow_change_sdr);
  return (
    <div className="flex flex-col gap-5">
      <Summary
        lines={[
          top && change !== null
            ? `The biggest driver this week: ${String(top.vessel_category)}, ${change >= 0 ? "up" : "down"} ${formatValue(Math.abs(change), "SDR")} SDR on last week.`
            : "No category moved this week.",
          `${rows.filter((r) => (num(r.budget_variance_sdr) ?? 0) < 0).length} of ${rows.length} categories billed below budget.`,
        ]}
      />
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Billing against budget by vessel category</CardTitle>
          <CardDescription className="font-mono text-xs">
            {cat.data.source?.name} — {cat.data.source?.filter}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SeriesChart
            categories={cats}
            series={series}
            unit="SDR"
            kind="bar"
            label="Billing against budget by vessel category"
          />
          <SeriesTable categories={cats} series={series} unit="SDR" />
        </CardContent>
      </Card>
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
  const r = weekly.data?.rows?.[0] as Row | undefined;
  if (!weekly.data || !overdue.data) return <Loading error={weekly.error ?? overdue.error} />;
  const buckets = AGING.map(([f, label]) => [label, num(r?.[f])] as const);
  const largest = [...buckets].filter((b) => b[1] !== null).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))[0];
  const series = [{ name: "Receivables", values: buckets.map((b) => b[1]) }];
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
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Receivables by age</CardTitle>
          </CardHeader>
          <CardContent>
            <SeriesChart
              categories={buckets.map((b) => b[0])}
              series={series}
              unit="SDR"
              kind="bar"
              label="Receivables by age"
            />
          </CardContent>
        </Card>
        <div className="grid grid-cols-2 gap-4 self-start">
          <Kpi label="Receivables" data={weekly.data} row={r} field="ar_sdr" unit="SDR" />
          <Kpi label="Overdue" data={weekly.data} row={r} field="overdue_sdr" unit="SDR" />
          <Kpi label="Newly overdue" data={weekly.data} row={r} field="overdue_new_sdr" unit="SDR" />
          <Kpi label="Overdue paid" data={weekly.data} row={r} field="overdue_paid_sdr" unit="SDR" />
        </div>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Overdue invoices</CardTitle>
          <CardDescription className="font-mono text-xs">{overdue.data.source?.name}</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-xs text-muted-foreground">
                <th className="py-2 pe-3 text-start font-medium">Invoice</th>
                <th className="py-2 pe-3 text-start font-medium">Customer</th>
                <th className="py-2 pe-3 text-end font-medium">Amount (SDR)</th>
                <th className="py-2 pe-3 text-end font-medium">Days past due</th>
              </tr>
            </thead>
            <tbody>
              {((overdue.data.rows ?? []) as Row[]).slice(0, 15).map((o) => (
                <tr key={String(o.invoice_number)} className="border-b last:border-0">
                  <td className="py-2 pe-3 font-mono text-xs">{String(o.invoice_number)}</td>
                  <td className="py-2 pe-3">{String(o.customer_name ?? "")}</td>
                  <td className="num py-2 pe-3 text-end">{formatValue(num(o.amount_sdr), "SDR")}</td>
                  <td className="num py-2 pe-3 text-end">{String(o.days_past_due ?? "")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

function Customers({ week }: { week: number }) {
  const cust = useDataset("customers", week, 20);
  if (!cust.data) return <Loading error={cust.error} />;
  const rows = (cust.data.rows ?? []) as Row[];
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
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Customers — trailing 13 weeks</CardTitle>
          <CardDescription className="font-mono text-xs">
            {cust.data.source?.name} — {cust.data.source?.filter}
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-xs text-muted-foreground">
                <th className="py-2 pe-3 text-start font-medium">#</th>
                <th className="py-2 pe-3 text-start font-medium">Customer</th>
                <th className="py-2 pe-3 text-end font-medium">Share</th>
                <th className="py-2 pe-3 text-end font-medium">Receivables</th>
                <th className="py-2 pe-3 text-end font-medium">Overdue</th>
                <th className="py-2 pe-3 text-start font-medium">Watchlist</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={String(c.customer_id)} className="border-b last:border-0">
                  <td className="num py-2 pe-3">{String(c.rank_13w ?? "")}</td>
                  <td className="py-2 pe-3">{String(c.customer_name ?? "")}</td>
                  <td className="num py-2 pe-3 text-end">{formatValue(num(c.share_13w_pct), "%")}</td>
                  <td className="num py-2 pe-3 text-end">{formatValue(num(c.ar_sdr), "SDR")}</td>
                  <td className="num py-2 pe-3 text-end">{formatValue(num(c.overdue_sdr), "SDR")}</td>
                  <td className="py-2 pe-3">
                    {c.is_watchlist ? (
                      <span className="rounded-full bg-waiting-wash px-2 py-0.5 text-xs text-waiting-ink">
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
        </CardContent>
      </Card>
    </div>
  );
}

function Exceptions({ week }: { week: number }) {
  const audit = useQuery({ queryKey: ["finance", "audit", week], queryFn: () => getAudit({ week }) });
  if (!audit.data) return <Loading error={audit.error} />;
  const a = audit.data;
  return (
    <div className="flex flex-col gap-5">
      <Summary
        lines={[
          `${a.invoices_flagged ?? 0} of ${a.invoices_checked ?? 0} invoices of the week have a finding.`,
          a.invoices_manual_review
            ? `${a.invoices_manual_review} need a person's review (a tariff Notes rule may apply).`
            : "No invoice waits for a manual review.",
        ]}
      />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card className="gap-1 py-4">
          <CardHeader className="px-4">
            <CardDescription>Checked</CardDescription>
            <CardTitle className="num text-xl">{a.invoices_checked ?? 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card className="gap-1 py-4">
          <CardHeader className="px-4">
            <CardDescription>With a finding</CardDescription>
            <CardTitle className="num text-xl">{a.invoices_flagged ?? 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card className="gap-1 py-4">
          <CardHeader className="px-4">
            <CardDescription>Amount at stake</CardDescription>
            <CardTitle className="num text-xl">
              {formatValue(a.amount_at_stake_sdr ?? null, "SDR")} SDR
            </CardTitle>
          </CardHeader>
        </Card>
        <Card className="gap-1 py-4">
          <CardHeader className="px-4">
            <CardDescription>Manual review</CardDescription>
            <CardTitle className="num text-xl">{a.invoices_manual_review ?? 0}</CardTitle>
          </CardHeader>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Findings</CardTitle>
          <CardDescription className="font-mono text-xs">
            {a.source?.name} — {a.source?.filter}
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-xs text-muted-foreground">
                <th className="py-2 pe-3 text-start font-medium">Invoice</th>
                <th className="py-2 pe-3 text-start font-medium">Check</th>
                <th className="py-2 pe-3 text-start font-medium">Probable cause</th>
                <th className="py-2 pe-3 text-end font-medium">Difference (SDR)</th>
              </tr>
            </thead>
            <tbody>
              {((a.rows ?? []) as Row[]).slice(0, 20).map((f, i) => (
                <tr key={`${String(f.invoice_number)}-${i}`} className="border-b last:border-0">
                  <td className="py-2 pe-3 font-mono text-xs">{String(f.invoice_number)}</td>
                  <td className="py-2 pe-3 font-mono text-xs">{String(f.check_code ?? "")}</td>
                  <td className="py-2 pe-3">{String(f.probable_cause ?? "")}</td>
                  <td className="num py-2 pe-3 text-end">{formatValue(num(f.difference_sdr), "SDR")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {(a.rows ?? []).length === 0 ? (
            <p className="py-3 text-sm text-muted-foreground">No finding this week.</p>
          ) : null}
        </CardContent>
      </Card>
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
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi
          label="Billed this week"
          data={weekly.data}
          row={r}
          field="billed_sdr"
          unit="SDR"
          change="billed_wow_pct"
        />
        <Kpi label="Billed, 13 weeks" data={weekly.data} row={r} field="billed_13w_sdr" unit="SDR" />
        <Kpi
          label="Overdue"
          data={weekly.data}
          row={r}
          field="overdue_sdr"
          unit="SDR"
          change="overdue_wow_pct"
        />
        <Kpi label="DSO" data={weekly.data} row={r} field="dso_days" unit="days" />
      </div>
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
          <h1 className="text-2xl font-semibold">Finance</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            The same views as Power BI and the weekly pack. Hover a number for its source.
          </p>
        </div>
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
            <Revenue week={week} />
          </TabsContent>
          <TabsContent value="receivables" className="mt-5">
            <Receivables week={week} />
          </TabsContent>
          <TabsContent value="customers" className="mt-5">
            <Customers week={week} />
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
