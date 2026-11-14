"use client";
// One chart component for the web (Frontend plan §6.5, owner F3 = Recharts 3.10.1): the views' ViewSpec and the pack's
// `charts_drawn` both draw through it. dataviz rules: one axis and one unit per chart, thin marks with rounded data
// ends, a legend for two series or more, recessive grid, a tooltip, `null` = a gap (never zero), time left → right.
// The values are drawn as the API gave them; the browser only formats them.
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type Series = { name: string; values: (number | null)[] };
export type Unit = "SDR" | "%" | "days" | null;

const PALETTE = ["var(--chart-1)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];
const colorOf = (name: string, i: number) =>
  /budget/i.test(name) ? "var(--chart-2)" : PALETTE[i % PALETTE.length];

export function formatValue(v: number | null | undefined, unit: Unit): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (unit === "%") return `${v.toFixed(1)}%`;
  if (unit === "days") return `${v.toFixed(1)} d`;
  const abs = Math.abs(v);
  if (abs >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${(v / 1e3).toFixed(1)}k`;
  return v.toFixed(abs < 10 ? 2 : 0);
}

export function SeriesChart({
  categories,
  series,
  unit,
  kind,
  label,
  height = 280,
}: {
  categories: string[];
  series: Series[];
  unit: Unit;
  kind: "line" | "bar";
  label: string;
  height?: number;
}) {
  const data = categories.map((c, i) =>
    Object.fromEntries([["category", c], ...series.map((s, k) => [`s${k}`, s.values[i] ?? null])]),
  );
  const common = {
    data,
    margin: { top: 8, right: 8, bottom: 4, left: 4 },
  };
  const axes = (
    <>
      <CartesianGrid stroke="var(--border)" vertical={false} />
      <XAxis
        dataKey="category"
        tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
        tickLine={false}
        axisLine={{ stroke: "var(--border)" }}
        interval="preserveStartEnd"
        minTickGap={12}
      />
      <YAxis
        width={56}
        tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
        tickLine={false}
        axisLine={false}
        tickFormatter={(v: number) => formatValue(v, unit)}
      />
      <Tooltip
        formatter={(v, name) => [formatValue(typeof v === "number" ? v : null, unit), String(name)]}
        contentStyle={{ borderRadius: 8, border: "1px solid var(--border)", fontSize: 12 }}
      />
      {series.length > 1 ? <Legend wrapperStyle={{ fontSize: 12 }} iconType="circle" iconSize={8} /> : null}
    </>
  );
  return (
    <figure role="img" aria-label={label} className="w-full">
      <ResponsiveContainer width="100%" height={height}>
        {kind === "line" ? (
          <LineChart {...common}>
            {axes}
            {series.map((s, k) => (
              <Line
                key={s.name}
                dataKey={`s${k}`}
                name={s.name}
                stroke={colorOf(s.name, k)}
                strokeWidth={2}
                strokeDasharray={/budget/i.test(s.name) ? "6 4" : undefined}
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        ) : (
          <BarChart {...common} barGap={2}>
            {axes}
            {series.map((s, k) => (
              <Bar
                key={s.name}
                dataKey={`s${k}`}
                name={s.name}
                fill={colorOf(s.name, k)}
                radius={[4, 4, 0, 0]}
                isAnimationActive={false}
              />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
    </figure>
  );
}

/** The same numbers as a table (accessibility; and what the tests compare with the API's values). */
export function SeriesTable({
  categories,
  series,
  unit,
}: {
  categories: string[];
  series: Series[];
  unit: Unit;
}) {
  return (
    <details className="mt-3 text-sm">
      <summary className="cursor-pointer text-xs text-muted-foreground">Show the numbers</summary>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b text-muted-foreground">
              <th className="py-1.5 pe-3 text-start font-medium" scope="col">
                &nbsp;
              </th>
              {series.map((s) => (
                <th key={s.name} className="py-1.5 pe-3 text-end font-medium" scope="col">
                  {s.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {categories.map((c, i) => (
              <tr key={c} className="border-b last:border-0">
                <th scope="row" className="py-1.5 pe-3 text-start font-normal">
                  {c}
                </th>
                {series.map((s) => (
                  <td key={s.name} className="num py-1.5 pe-3 text-end" data-value={s.values[i] ?? ""}>
                    {formatValue(s.values[i], unit)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
