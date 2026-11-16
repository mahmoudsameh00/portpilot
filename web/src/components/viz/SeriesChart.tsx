"use client";
// One chart component for the web (Frontend plan §6.5, owner F3 = Recharts 3.10.1): the views' ViewSpec and the pack's
// `charts_drawn` both draw through it. dataviz rules: one axis and one unit per chart, thin marks with rounded data
// ends, a legend for two series or more, recessive grid, a tooltip, `null` = a gap (never zero), time left → right.
// The values are drawn as the API gave them; the browser only formats them.
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
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
  highlight,
}: {
  categories: string[];
  series: Series[];
  unit: Unit;
  /** amendment 1 (D-WD-5): "combo" = the first series as bars, the others as lines (billed bars, budget dashed, collected);
   * "area" = one series over time. */
  kind: "line" | "bar" | "combo" | "area";
  label: string;
  height?: number;
  /** the category to emphasise (the report week): its bar in colour, the others muted; a circle on a line (as the deck
   * draws it); a hairline on an area */
  highlight?: number;
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
        // a marked line ends inside the plot: Recharts clips a dot that sits on the plot's edge
        {...(kind === "line" && highlight !== undefined ? { padding: { left: 8, right: 12 } } : {})}
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
  const hl = highlight !== undefined && highlight >= 0 ? categories[highlight] : undefined;
  const mark = hl ? (
    <ReferenceLine x={hl} stroke="var(--marker)" strokeWidth={1.5} ifOverflow="extendDomain" />
  ) : null;
  return (
    <figure role="img" aria-label={label} className="w-full" data-kind={kind}>
      <ResponsiveContainer width="100%" height={height}>
        {kind === "combo" ? (
          <ComposedChart {...common}>
            {axes}
            {series.map((s, k) =>
              k === 0 ? (
                <Bar
                  key={s.name}
                  dataKey="s0"
                  name={s.name}
                  fill="var(--chart-1)"
                  radius={[4, 4, 0, 0]}
                  isAnimationActive={false}
                >
                  {categories.map((c, i) => (
                    <Cell
                      key={c}
                      fill={hl === undefined || i === highlight ? "var(--chart-1)" : "var(--chart-muted)"}
                    />
                  ))}
                </Bar>
              ) : (
                <Line
                  key={s.name}
                  dataKey={`s${k}`}
                  name={s.name}
                  stroke={/budget/i.test(s.name) ? "var(--chart-2)" : "var(--chart-3)"}
                  strokeWidth={2}
                  strokeDasharray={/budget/i.test(s.name) ? "6 4" : undefined}
                  dot={false}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              ),
            )}
          </ComposedChart>
        ) : kind === "area" ? (
          <AreaChart {...common}>
            {axes}
            {mark}
            {series.map((s, k) => (
              <Area
                key={s.name}
                dataKey={`s${k}`}
                name={s.name}
                stroke="var(--chart-1)"
                strokeWidth={2}
                fill="var(--chart-1)"
                fillOpacity={0.12}
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </AreaChart>
        ) : kind === "line" ? (
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
                // the report week as the deck marks it: a 10 px circle in the marker orange on the first series
                dot={
                  k === 0 && hl !== undefined
                    ? (p: { cx?: number; cy?: number; index?: number }) =>
                        p.index === highlight && p.cx !== undefined && p.cy !== undefined ? (
                          <circle
                            key="report-week"
                            data-highlight="report-week"
                            cx={p.cx}
                            cy={p.cy}
                            r={5}
                            fill="var(--marker)"
                            stroke="var(--card)"
                            strokeWidth={2}
                          />
                        ) : (
                          <g key={`d${p.index}`} />
                        )
                    : false
                }
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
      <div className="mt-2 overflow-x-auto" role="region" aria-label="The numbers" tabIndex={0}>
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
