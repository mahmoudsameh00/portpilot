// Chart forms chosen by the data's job (web dashboards plan amendment 1, D-WD-5, owner 2026-11-15; dataviz skill):
// a coloured change on the KPI tiles, bullet bars (value against a target tick), ranked horizontal bars with one
// emphasised item, a segmented share bar for a whole in ≤ 4 parts, a stacked aging bar on an ordinal ramp, a meter
// and a small diverging bar. Plain HTML: widths are geometry only — every printed number is a view's value, formatted
// (ADR-047). Colour never carries meaning alone: an icon, a sign or a label goes with it; every mark has a hover title.
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatValue, type Unit } from "@/components/viz/SeriesChart";

const pos = (v: number | null | undefined) =>
  typeof v === "number" && Number.isFinite(v) ? Math.max(v, 0) : 0;
const fmt = (v: number | null | undefined, unit: Unit) =>
  unit === "SDR" ? `${formatValue(v, unit)} SDR` : formatValue(v, unit);

/** The week-on-week change of a KPI: green when the move is good for the business, orange when bad (a fixed rule per
 * KPI: billed up is good, overdue up is bad); the arrow and the sign carry the direction for colour-blind readers. */
export function Delta({
  value,
  unit,
  goodWhen,
  suffix = "on last week",
}: {
  value: number | null;
  unit: Unit;
  goodWhen: "up" | "down";
  suffix?: string;
}) {
  if (value === null) return <span className="text-muted-foreground">no change data</span>;
  const good = value === 0 ? null : value > 0 === (goodWhen === "up");
  const Icon = value > 0 ? ArrowUpRight : value < 0 ? ArrowDownRight : Minus;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 font-medium",
        good === null ? "text-muted-foreground" : good ? "text-approved-ink" : "text-alert-ink",
      )}
      data-tone={good === null ? "flat" : good ? "good" : "bad"}
    >
      <Icon className="size-3.5" aria-hidden />
      {`${value > 0 ? "+" : ""}${formatValue(value, unit)}`}
      <span className="font-normal text-muted-foreground">{suffix}</span>
      <span className="sr-only">{good === null ? "" : good ? "(a good move)" : "(a bad move)"}</span>
    </span>
  );
}

export type BulletRow = {
  label: string;
  value: number | null;
  target: number | null;
  /** the view's own variance, printed beside the bar */
  note?: string;
};

/** Value bars against a target tick, one shared scale; rows under their target drawn in the alert orange. */
export function BulletBars({
  rows,
  unit,
  valueName = "Billed",
  targetName = "Budget",
  label,
}: {
  rows: BulletRow[];
  unit: Unit;
  valueName?: string;
  targetName?: string;
  label: string;
}) {
  const max = Math.max(1, ...rows.flatMap((r) => [pos(r.value), pos(r.target)]));
  return (
    <figure aria-label={label} className="flex flex-col gap-3">
      <ul className="flex flex-col gap-3">
        {rows.map((r) => {
          const below = r.value !== null && r.target !== null && r.value < r.target;
          return (
            <li
              key={r.label}
              data-below={below || undefined}
              className="grid grid-cols-1 gap-1 sm:grid-cols-[minmax(7rem,11rem)_minmax(0,1fr)] sm:items-center sm:gap-3"
              title={`${r.label}: ${valueName.toLowerCase()} ${fmt(r.value, unit)}, ${targetName.toLowerCase()} ${fmt(r.target, unit)}`}
            >
              <span className="truncate text-sm">{r.label}</span>
              <span className="flex min-w-0 items-center gap-3">
                <span className="relative h-5 min-w-0 flex-1 rounded-[4px] bg-muted">
                  <span
                    className={cn(
                      "absolute inset-y-0 start-0 rounded-[4px]",
                      below ? "bg-alert" : "bg-chart-1",
                    )}
                    style={{ width: `${(pos(r.value) / max) * 100}%` }}
                  />
                  {r.target !== null ? (
                    <span
                      className="absolute -inset-y-1 w-[3px] rounded-full bg-foreground"
                      style={{ insetInlineStart: `calc(${(pos(r.target) / max) * 100}% - 1.5px)` }}
                      aria-hidden
                    />
                  ) : null}
                </span>
                <span className="num w-28 shrink-0 text-end text-xs">
                  <span className="block font-semibold text-foreground">{fmt(r.value, unit)}</span>
                  {r.note ? (
                    <span className={cn("block", below ? "text-alert-ink" : "text-muted-foreground")}>
                      {r.note}
                    </span>
                  ) : null}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
      <figcaption className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-[3px] bg-chart-1" /> {valueName}
        </span>
        {rows.some((r) => r.value !== null && r.target !== null && r.value < r.target) ? (
          <span className="flex items-center gap-1.5">
            <span className="inline-block size-2.5 rounded-[3px] bg-alert" /> {valueName} below{" "}
            {targetName.toLowerCase()}
          </span>
        ) : null}
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-[3px] rounded-full bg-foreground" /> {targetName}
        </span>
      </figcaption>
    </figure>
  );
}

export type RankedRow = {
  label: string;
  value: number | null;
  compare?: number | null;
  /** emphasised (in colour) — the rest are muted */
  highlight?: boolean;
  /** drawn in the alert orange with this tag beside the name (e.g. "watch") */
  flag?: string;
};

/** Horizontal bars, largest first, one shared scale: long names stay readable on a phone. The one item that matters
 * is in colour, the rest muted; with a compare week a light bar sits under each row's bar. */
export function RankedBars({
  rows,
  unit,
  label,
  seriesName,
  compareName,
}: {
  rows: RankedRow[];
  unit: Unit;
  label: string;
  seriesName: string;
  compareName?: string;
}) {
  const withCompare = compareName !== undefined;
  const max = Math.max(1, ...rows.flatMap((r) => [pos(r.value), pos(r.compare)]));
  const anyHighlight = rows.some((r) => r.highlight);
  return (
    <figure aria-label={label} className="flex flex-col gap-2">
      <ul className="flex flex-col gap-2.5">
        {rows.map((r) => {
          const tone = r.flag
            ? "bg-alert"
            : withCompare || !anyHighlight || r.highlight
              ? "bg-chart-1"
              : "bg-chart-muted";
          return (
            <li
              key={r.label}
              data-emphasis={r.flag ? "flag" : r.highlight ? "highlight" : undefined}
              className="grid grid-cols-1 gap-1 sm:grid-cols-[minmax(7rem,12rem)_minmax(0,1fr)] sm:items-center sm:gap-3"
              title={`${r.label}: ${fmt(r.value, unit)}${withCompare ? ` (${compareName}: ${fmt(r.compare, unit)})` : ""}`}
            >
              <span className="flex min-w-0 items-center gap-2 text-sm">
                <span className={cn("truncate", r.highlight || r.flag ? "font-medium" : "")}>{r.label}</span>
                {r.flag ? (
                  <span className="shrink-0 rounded-full bg-alert-wash px-1.5 py-px text-[11px] text-alert-ink">
                    {r.flag}
                  </span>
                ) : null}
              </span>
              <span className="flex min-w-0 items-center gap-3">
                <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
                  <span
                    className={cn("block h-3.5 rounded-e-[4px]", tone)}
                    style={{ width: `${Math.max((pos(r.value) / max) * 100, 0.5)}%` }}
                  />
                  {withCompare ? (
                    <span
                      className="block h-2 rounded-e-[4px] bg-chart-compare"
                      style={{ width: `${Math.max((pos(r.compare) / max) * 100, 0.5)}%` }}
                    />
                  ) : null}
                </span>
                <span className="num w-20 shrink-0 text-end text-xs">
                  <span className="block font-semibold text-foreground">{formatValue(r.value, unit)}</span>
                  {withCompare ? (
                    <span className="block text-muted-foreground">
                      {formatValue(r.compare ?? null, unit)}
                    </span>
                  ) : null}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
      {withCompare ? (
        <figcaption className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="inline-block size-2.5 rounded-[3px] bg-chart-1" /> {seriesName}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block size-2.5 rounded-[3px] bg-chart-compare" /> {compareName}
          </span>
          {unit ? <span>{unit}</span> : null}
        </figcaption>
      ) : null}
    </figure>
  );
}

/** Categorical slots in fixed order (validated: blue / teal / amber / violet on white), never cycled. */
const SLOTS = ["bg-chart-1", "bg-chart-3", "bg-chart-4", "bg-chart-5"] as const;
export const SEGMENT_MAX = SLOTS.length;

export type Part = { label: string; value: number | null; share?: number | null; className?: string };

/** One whole in ≤ 4 parts at a glance: a tall segmented bar (each part's share printed on it where it fits) and a
 * legend with every part's value. The parts are the view's rows; the widths are drawn from their values. */
export function SegmentBar({
  parts,
  unit,
  label,
  thin = false,
  total,
}: {
  parts: Part[];
  unit: Unit;
  label: string;
  thin?: boolean;
  total?: { label: string; text: string };
}) {
  const sum = parts.reduce((s, p) => s + pos(p.value), 0) || 1;
  return (
    <figure aria-label={label} className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <div className={cn("flex min-w-0 flex-1 gap-[2px]", thin ? "h-5" : "h-10")}>
          {parts.map((p, i) => {
            const w = (pos(p.value) / sum) * 100;
            const text = p.share !== undefined && p.share !== null ? formatValue(p.share, "%") : null;
            return (
              <span
                key={p.label}
                title={`${p.label}: ${fmt(p.value, unit)}${text ? ` (${text})` : ""}`}
                className={cn(
                  "flex min-w-[3px] items-center justify-center overflow-hidden rounded-[4px] text-xs font-semibold",
                  p.className ?? SLOTS[i % SLOTS.length],
                )}
                style={{ width: `${w}%` }}
              >
                {!thin && text && w >= 14 ? (
                  // a white pill keeps the text ≥ 4.5:1 on every fill (white on the blue is 4.42:1)
                  <span className="num rounded-[3px] bg-card px-1 py-px text-foreground">{text}</span>
                ) : null}
              </span>
            );
          })}
        </div>
        {total ? (
          <span className="num shrink-0 text-end text-xs">
            <span className="block text-muted-foreground">{total.label}</span>
            <span className="block text-sm font-semibold">{total.text}</span>
          </span>
        ) : null}
      </div>
      <figcaption>
        <ul className="grid grid-cols-1 gap-x-6 gap-y-1.5 text-sm sm:grid-cols-2">
          {parts.map((p, i) => (
            <li key={p.label} className="flex items-center gap-2">
              <span
                className={cn(
                  "inline-block size-2.5 shrink-0 rounded-[3px]",
                  p.className ?? SLOTS[i % SLOTS.length],
                )}
              />
              <span className="me-auto truncate">{p.label}</span>
              <span className="num font-medium">{fmt(p.value, unit)}</span>
              {p.share !== undefined && p.share !== null ? (
                <span className="num w-12 text-end text-xs text-muted-foreground">
                  {formatValue(p.share, "%")}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      </figcaption>
    </figure>
  );
}

/** Receivables by age: an ordinal blue ramp (older = darker), the oldest bucket breaking it in the marker orange. */
export const AGING_TONES = ["bg-ramp-1", "bg-ramp-2", "bg-ramp-3", "bg-ramp-4", "bg-marker"] as const;

/** One ratio against its whole (0–100 %): a track and a fill; under `alertBelow` the fill is orange with a label. */
export function Meter({
  value,
  label,
  alertBelow,
  detail,
  of,
}: {
  value: number | null;
  label: string;
  alertBelow?: number;
  detail?: string;
  /** a count against its whole (both from the view): drawn as their ratio, printed as "part of whole" */
  of?: { part: number; whole: number; tone?: "alert" };
}) {
  const warn = value !== null && alertBelow !== undefined && value < alertBelow;
  const low = warn || of?.tone === "alert";
  const width = of ? (of.whole > 0 ? (of.part / of.whole) * 100 : 0) : Math.min(pos(value), 100);
  return (
    <div className="flex flex-col gap-1.5" data-low={low || undefined}>
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="text-lg font-semibold">
          {of ? `${of.part} of ${of.whole}` : formatValue(value, "%")}
        </span>
      </div>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={of ? of.whole : 100}
        aria-valuenow={of ? of.part : (value ?? undefined)}
        className="h-2.5 rounded-full bg-muted"
      >
        <div
          className={cn("h-full rounded-full", low ? "bg-alert" : "bg-chart-1")}
          style={{ width: `${width}%` }}
        />
      </div>
      {detail || warn ? (
        <p className={cn("text-xs", warn ? "text-alert-ink" : "text-muted-foreground")}>
          {warn ? `Below ${alertBelow}%. ` : ""}
          {detail}
        </p>
      ) : null}
    </div>
  );
}

/** A small diverging bar in a table cell: above zero to the end side in orange, below zero to the start side in blue,
 * around a neutral centre line; the signed value stays printed beside it. */
export function DivergingCell({ value, max, unit }: { value: number | null; max: number; unit: Unit }) {
  const v = value ?? 0;
  const w = max > 0 ? (Math.min(Math.abs(v), max) / max) * 50 : 0;
  return (
    <span className="flex items-center justify-end gap-2">
      <span className="num">{`${v > 0 ? "+" : ""}${formatValue(value, unit)}`}</span>
      <span className="relative hidden h-2.5 w-16 shrink-0 sm:block" aria-hidden>
        <span className="absolute inset-y-[-2px] start-1/2 w-px bg-border" />
        <span
          className={cn("absolute inset-y-0 rounded-[3px]", v >= 0 ? "bg-alert" : "bg-chart-1")}
          style={
            v >= 0 ? { insetInlineStart: "50%", width: `${w}%` } : { insetInlineEnd: "50%", width: `${w}%` }
          }
        />
      </span>
    </span>
  );
}
