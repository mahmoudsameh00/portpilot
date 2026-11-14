// Small hand-drawn SVG charts for the concept (F5 moves the real charts to Recharts). dataviz rules: one axis,
// thin marks with 4 px rounded data-ends, a 2 px surface gap between bars, text in text colours (never the series
// colour), a legend for two series, a <title> hover layer on every mark. Time runs left → right.
import { cn } from "@/lib/utils";

export function Sparkline({
  values,
  className,
  tone = "primary",
}: {
  values: number[];
  className?: string;
  tone?: "primary" | "alert" | "muted";
}) {
  const w = 120;
  const h = 36;
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const x = (i: number) => (i / (values.length - 1)) * (w - 4) + 2;
  const y = (v: number) => h - 4 - ((v - lo) / (hi - lo || 1)) * (h - 8);
  const line = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const stroke =
    tone === "alert" ? "var(--alert)" : tone === "muted" ? "var(--muted-foreground)" : "var(--chart-1)";
  const last = values.length - 1;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={cn("h-9 w-full", className)} aria-hidden>
      <path d={`${line} L${x(last)} ${h} L${x(0)} ${h} Z`} fill={stroke} opacity="0.1" />
      <path
        d={line}
        fill="none"
        stroke={stroke}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={x(last)} cy={y(values[last]!)} r="3" fill={stroke} stroke="var(--card)" strokeWidth="2" />
    </svg>
  );
}

export function BillingChart({
  weeks,
  billed,
  budget,
  unit = "M SDR",
  compact = false,
}: {
  weeks: string[];
  billed: number[];
  budget: number[];
  unit?: string;
  compact?: boolean;
}) {
  const W = compact ? 820 : 520;
  const H = compact ? 230 : 240;
  const pad = { top: 10, right: 8, bottom: 26, left: 34 };
  const lo = 7;
  const hi = 9;
  const step = (W - pad.left - pad.right) / weeks.length;
  const x = (i: number) => pad.left + step * (i + 0.5);
  const y = (v: number) => pad.top + (H - pad.top - pad.bottom) * (1 - (v - lo) / (hi - lo));
  const bw = step - 4; // 2 px surface gap each side
  const last = weeks.length - 1;
  const budgetPath = budget.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  return (
    <figure className="w-full">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label="Billed against budget by week, million SDR"
      >
        {[7, 7.5, 8, 8.5, 9].map((g) => (
          <g key={g}>
            <line
              x1={pad.left}
              x2={W - pad.right}
              y1={y(g)}
              y2={y(g)}
              stroke="var(--border)"
              strokeWidth="1"
            />
            <text
              x={pad.left - 6}
              y={y(g) + 4}
              textAnchor="end"
              fontSize="11"
              className="fill-muted-foreground num"
            >
              {g.toFixed(1)}
            </text>
          </g>
        ))}
        {billed.map((v, i) => {
          const top = y(v);
          const base = y(lo);
          const r = Math.min(4, bw / 2);
          return (
            <path
              key={weeks[i]}
              d={`M${x(i) - bw / 2} ${base} V${top + r} Q${x(i) - bw / 2} ${top} ${x(i) - bw / 2 + r} ${top} H${x(i) + bw / 2 - r} Q${x(i) + bw / 2} ${top} ${x(i) + bw / 2} ${top + r} V${base} Z`}
              fill="var(--chart-1)"
              opacity={i === last ? 1 : 0.5}
            >
              <title>{`${weeks[i]}: billed ${v.toFixed(2)} ${unit}, budget ${budget[i]?.toFixed(2)} ${unit}`}</title>
            </path>
          );
        })}
        <path d={budgetPath} fill="none" stroke="var(--chart-2)" strokeWidth="2" strokeDasharray="6 4" />
        {weeks.map((w, i) =>
          i % 2 === 1 || i === last ? (
            <text
              key={w}
              x={x(i)}
              y={H - 8}
              textAnchor="middle"
              fontSize="11"
              className={i === last ? "fill-foreground num font-semibold" : "fill-muted-foreground num"}
            >
              {w}
            </text>
          ) : null,
        )}
        <rect
          x={x(last) - bw / 2}
          y={H - pad.bottom + 2}
          width={bw}
          height="3"
          rx="1.5"
          fill="var(--marker)"
        />
      </svg>
      <figcaption className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-[3px] bg-chart-1" /> Billed
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-4 border-t-2 border-dashed border-chart-2" /> Budget
        </span>
        <span>{unit}</span>
      </figcaption>
    </figure>
  );
}

export type Blip = {
  vessel: string;
  text: string;
  level: "high" | "medium" | "low";
  angle: number;
  dist: number;
};
const LEVEL_FILL = { high: "var(--alert)", medium: "var(--waiting)", low: "var(--chart-1)" } as const;

export function Radar({ blips }: { blips: Blip[] }) {
  const R = 90;
  const c = 100;
  return (
    <svg viewBox="0 0 200 200" className="size-full" role="img" aria-label="Voyage alerts by severity">
      <defs>
        <linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="var(--chart-1)" stopOpacity="0" />
          <stop offset="1" stopColor="var(--chart-1)" stopOpacity="0.28" />
        </linearGradient>
      </defs>
      {[1, 0.66, 0.33].map((k) => (
        <circle key={k} cx={c} cy={c} r={R * k} fill="none" stroke="var(--border)" strokeWidth="1" />
      ))}
      <line x1={c - R} x2={c + R} y1={c} y2={c} stroke="var(--border)" />
      <line y1={c - R} y2={c + R} x1={c} x2={c} stroke="var(--border)" />
      <g className="radar-sweep">
        <path
          d={`M${c} ${c} L${c + R} ${c} A${R} ${R} 0 0 0 ${c + R * Math.cos(-0.9)} ${c + R * Math.sin(-0.9)} Z`}
          fill="url(#sweep)"
        />
      </g>
      {blips.map((b, i) => {
        const a = (b.angle * Math.PI) / 180;
        const bx = c + Math.cos(a) * R * b.dist;
        const by = c + Math.sin(a) * R * b.dist;
        return (
          <g key={`${b.vessel}-${i}`}>
            {b.level === "high" ? (
              <circle cx={bx} cy={by} r="5" fill={LEVEL_FILL.high} className="port-pulse" />
            ) : null}
            <circle
              cx={bx}
              cy={by}
              r={b.level === "high" ? 4.5 : 3.5}
              fill={LEVEL_FILL[b.level]}
              stroke="var(--card)"
              strokeWidth="2"
            >
              <title>{`${b.vessel} — ${b.text} (${b.level})`}</title>
            </circle>
          </g>
        );
      })}
      <circle cx={c} cy={c} r="3" fill="var(--foreground)" />
    </svg>
  );
}

/** Overdue receivables by age: each bucket is a row of containers on a deck (one box = 0.5M SDR). */
export function ContainerStacks({ buckets }: { buckets: { bucket: string; value: number }[] }) {
  const unit = 0.5;
  const shades = ["bg-chart-1", "bg-chart-1/75", "bg-chart-1/50", "bg-marker"];
  return (
    <ul className="flex flex-col gap-3" aria-label="Overdue receivables by age bucket">
      {buckets.map((b, i) => {
        const full = Math.floor(b.value / unit);
        const part = (b.value - full * unit) / unit;
        return (
          <li
            key={b.bucket}
            className="grid grid-cols-[4.5rem_minmax(0,1fr)_3.5rem] items-center gap-3 text-sm"
            title={`${b.bucket}: ${b.value.toFixed(2)}M SDR overdue`}
          >
            <span className="text-muted-foreground">{b.bucket}</span>
            <span className="flex gap-[3px]">
              {Array.from({ length: full }, (_, k) => (
                <span key={k} className={cn("relative h-5 w-4 shrink-0 rounded-[3px] sm:w-5", shades[i])}>
                  <span className="absolute inset-y-1 start-1/2 w-px bg-card/40" />
                </span>
              ))}
              {part > 0.05 ? (
                <span
                  className={cn("h-5 shrink-0 rounded-[3px] opacity-60", shades[i])}
                  style={{ width: `${part * 1.25}rem` }}
                />
              ) : null}
            </span>
            <span className="num text-end font-semibold">{b.value.toFixed(2)}M</span>
          </li>
        );
      })}
    </ul>
  );
}

/** Suez against the Cape: two bars per measure on one shared scale per row (never a dual axis). */
export function RouteCompare({
  suez,
  cape,
}: {
  suez: { days: number; cost: number; distance: number };
  cape: { days: number; cost: number; distance: number };
}) {
  const rows = [
    { label: "Days", s: suez.days, c: cape.days, fmt: (v: number) => v.toFixed(1) },
    { label: "Cost (M SDR)", s: suez.cost, c: cape.cost, fmt: (v: number) => v.toFixed(2) },
    {
      label: "Distance (nm)",
      s: suez.distance,
      c: cape.distance,
      fmt: (v: number) => v.toLocaleString("en"),
    },
  ];
  return (
    <div className="flex flex-col gap-3">
      {rows.map((r) => {
        const max = Math.max(r.s, r.c);
        return (
          <div key={r.label}>
            <p className="mb-1 text-xs text-muted-foreground">{r.label}</p>
            {(
              [
                ["Suez", r.s, "bg-chart-1"],
                ["Cape", r.c, "bg-chart-2"],
              ] as const
            ).map(([name, v, color]) => (
              <div key={name} className="flex items-center gap-2 text-xs" title={`${name}: ${r.fmt(v)}`}>
                <span className="w-9 shrink-0 text-muted-foreground">{name}</span>
                <span className="h-2 rounded-full bg-muted" style={{ width: "100%" }}>
                  <span
                    className={cn("block h-2 rounded-full", color)}
                    style={{ width: `${(v / max) * 100}%` }}
                  />
                </span>
                <span className="num w-14 shrink-0 text-end font-medium text-foreground">{r.fmt(v)}</span>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
