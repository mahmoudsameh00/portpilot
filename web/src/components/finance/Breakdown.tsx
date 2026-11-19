"use client";
// "Break down by" (web dashboards plan §2c, owner decision D-WD-4, 2026-11-15): one chart card that shows the week's
// billing by the dimension the reader picks, in the measure they pick, optionally next to a compare week. The rows
// come from `finance.kpi_weekly_breakdown` (migration 029, M18) through GET /finance/breakdown; the web only picks and
// aligns rows (members matched by name between the two weeks), it adds no arithmetic (ADR-047). The choice lives in
// the URL (`<id>.dim`, `<id>.m`, `<id>.cmp`), so a link reopens the same view.
// Amendment 1 (D-WD-5 / D-WD-6, owner 2026-11-15): the form follows the rows — a whole in ≤ 4 parts is a segmented
// share bar (the view's `share_pct` on it), more members are ranked horizontal bars with the largest in colour and the
// rest muted, a compare week adds a light bar per member; the card downloads its own rows (and the compare week's).
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  breakdownApiV1FinanceBreakdownGet as getBreakdown,
  type BreakdownApiV1FinanceBreakdownGetDimension as Dimension,
  type FinanceWeek,
} from "@/api/generated/client";
import { FigureCard } from "@/components/finance/FigureCard";
import { RankedBars, SEGMENT_MAX, SegmentBar } from "@/components/viz/forms";
import { formatValue, type Unit } from "@/components/viz/SeriesChart";

type Row = Record<string, unknown>;
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

export const DIMENSIONS: { value: Dimension; label: string }[] = [
  { value: "vessel_category", label: "Vessel category" },
  { value: "toll_band", label: "Toll band" },
  { value: "route", label: "Route" },
  { value: "priced_condition", label: "Laden / ballast" },
  { value: "customer_segment", label: "Customer segment" },
  { value: "customer_country", label: "Customer country" },
  { value: "credit_rating", label: "Credit rating" },
];
const MEASURES: { value: "billed_sdr" | "invoices_billed" | "scnt_tons"; label: string; unit: Unit }[] = [
  { value: "billed_sdr", label: "Billed (SDR)", unit: "SDR" },
  { value: "invoices_billed", label: "Invoices", unit: null },
  { value: "scnt_tons", label: "SCNT tons", unit: null },
];
const TOP = 10;
const selectClass = "h-8 rounded-md border bg-background px-2 text-sm";

function useBreakdown(week: number | null, dimension: Dimension) {
  return useQuery({
    queryKey: ["finance", "breakdown", week, dimension],
    queryFn: () => getBreakdown({ week: week as number, dimension }),
    enabled: week !== null,
  });
}

export function BreakdownCard({
  id,
  week,
  weeks,
  title,
  initial,
}: {
  id: string;
  week: number;
  weeks: FinanceWeek[];
  title: string;
  initial: Dimension;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  // The choice is state first (read from the URL once), then mirrored to the URL: router.replace settles later,
  // so reading the URL back would let two quick changes overwrite each other.
  const [choice, setChoice] = useState<Record<"dim" | "m" | "cmp", string>>(() => ({
    dim: params.get(`${id}.dim`) ?? "",
    m: params.get(`${id}.m`) ?? "",
    cmp: params.get(`${id}.cmp`) ?? "",
  }));
  const dimension = (DIMENSIONS.find((d) => d.value === choice.dim)?.value ?? initial) as Dimension;
  const measure = MEASURES.find((m) => m.value === choice.m) ?? MEASURES[0]!;
  const cmpRaw = Number(choice.cmp);
  const compare = weeks.some((w) => w.report_week === cmpRaw) && cmpRaw !== week ? cmpRaw : null;
  const set = (key: "dim" | "m" | "cmp", value: string | null) => {
    const next = { ...choice, [key]: value ?? "" };
    setChoice(next);
    const q = new URLSearchParams(window.location.search);
    for (const [k, v] of Object.entries(next)) {
      if (v) q.set(`${id}.${k}`, v);
      else q.delete(`${id}.${k}`);
    }
    router.replace(`${pathname}?${q.toString()}`, { scroll: false });
  };

  const now = useBreakdown(week, dimension);
  const then = useBreakdown(compare, dimension);
  const rows = (now.data?.rows ?? []) as Row[];
  const top = rows.slice(0, TOP);
  const label = (w: number) => weeks.find((x) => x.report_week === w)?.iso_week_label ?? `W${w}`;
  const byMember = new Map(((then.data?.rows ?? []) as Row[]).map((r) => [String(r.member), r]));
  const series = [
    { name: label(week), values: top.map((r) => num(r[measure.value])) },
    ...(compare !== null
      ? [
          {
            name: label(compare),
            values: top.map((r) => num(byMember.get(String(r.member))?.[measure.value])),
          },
        ]
      : []),
  ];
  const dimLabel = DIMENSIONS.find((d) => d.value === dimension)?.label ?? dimension;
  const chartLabel = `${title}: ${measure.label} by ${dimLabel.toLowerCase()}`;

  const controls = (
    <div className="mt-2 flex flex-wrap gap-3">
      <label className="flex flex-col gap-1 text-xs text-muted-foreground">
        Break down by
        <select className={selectClass} value={dimension} onChange={(e) => set("dim", e.target.value)}>
          {DIMENSIONS.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted-foreground">
        Measure
        <select className={selectClass} value={measure.value} onChange={(e) => set("m", e.target.value)}>
          {MEASURES.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-muted-foreground">
        Compare with
        <select
          className={selectClass}
          value={compare ?? ""}
          onChange={(e) => set("cmp", e.target.value || null)}
        >
          <option value="">No other week</option>
          {weeks
            .filter((w) => w.report_week !== week)
            .map((w) => (
              <option key={w.report_week} value={w.report_week}>
                {w.iso_week_label}
              </option>
            ))}
        </select>
      </label>
    </div>
  );

  return (
    <FigureCard
      label={title}
      title={dimension === initial ? title : `${measure.label} by ${dimLabel.toLowerCase()}`}
      source={`${now.data?.source?.name ?? "finance.kpi_weekly_breakdown"} — ${now.data?.source?.filter ?? ""}`}
      of={{ figure: "breakdown", week, dimension, compare }}
      controls={controls}
    >
      {!now.data ? (
        now.error ? (
          <p role="alert" className="text-sm text-alert-ink">
            This breakdown could not be loaded.
          </p>
        ) : (
          <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden />
        )
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No invoice in this week.</p>
      ) : (
        <>
          {compare === null && rows.length <= SEGMENT_MAX ? (
            <SegmentBar
              label={chartLabel}
              unit={measure.unit}
              parts={rows.map((r) => ({
                label: String(r.member),
                value: num(r[measure.value]),
                // the view's share is of the week's billing: printed only when the bar is drawn in billing
                ...(measure.value === "billed_sdr" ? { share: num(r.share_pct) } : {}),
              }))}
            />
          ) : (
            <RankedBars
              label={chartLabel}
              unit={measure.unit}
              seriesName={label(week)}
              {...(compare !== null ? { compareName: label(compare) } : {})}
              rows={top.map((r, i, all) => ({
                label: String(r.member),
                value: num(r[measure.value]),
                compare: series[1]?.values[i] ?? null,
                // the largest member of the shown measure (a choice among the view's rows, no arithmetic)
                highlight:
                  compare === null &&
                  num(r[measure.value]) === Math.max(...all.map((x) => num(x[measure.value]) ?? -Infinity)),
              }))}
            />
          )}
          {rows.length > TOP ? (
            <p className="mt-1 text-xs text-muted-foreground">
              The chart shows the top {TOP} of {rows.length}; the table lists all of them.
            </p>
          ) : null}
          <details className="mt-3 text-sm">
            <summary className="cursor-pointer text-xs text-muted-foreground">Show the numbers</summary>
            <div
              className="mt-2 overflow-x-auto"
              role="region"
              aria-label={`${dimLabel} numbers`}
              tabIndex={0}
            >
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    <th scope="col" className="py-1.5 pe-3 text-start font-medium">
                      {dimLabel}
                    </th>
                    <th scope="col" className="py-1.5 pe-3 text-end font-medium">
                      Invoices
                    </th>
                    <th scope="col" className="py-1.5 pe-3 text-end font-medium">
                      Billed (SDR)
                    </th>
                    <th scope="col" className="py-1.5 pe-3 text-end font-medium">
                      SCNT tons
                    </th>
                    <th scope="col" className="py-1.5 pe-3 text-end font-medium">
                      Share
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={String(r.member)} className="border-b last:border-0">
                      <th scope="row" className="py-1.5 pe-3 text-start font-normal">
                        {String(r.member)}
                      </th>
                      <td className="num py-1.5 pe-3 text-end">{String(r.invoices_billed ?? "")}</td>
                      <td className="num py-1.5 pe-3 text-end" data-value={String(r.billed_sdr ?? "")}>
                        {formatValue(num(r.billed_sdr), "SDR")}
                      </td>
                      <td className="num py-1.5 pe-3 text-end">{formatValue(num(r.scnt_tons), null)}</td>
                      <td className="num py-1.5 pe-3 text-end">{formatValue(num(r.share_pct), "%")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}
    </FigureCard>
  );
}
