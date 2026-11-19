// Small hand-drawn SVG charts (sparkline, voyage radar; the dashboards use Recharts). dataviz rules: one axis,
// thin marks with 4 px rounded data-ends, a 2 px surface gap between bars, text in text colours (never the series
// colour), a <title> hover layer on every mark. Time runs left → right.
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
