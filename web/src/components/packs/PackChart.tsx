"use client";
// A pack chart as the deck draws it (`charts_drawn` = render.build_spec's own series): the web shows the same numbers
// the PPTX will show (Frontend plan F0), drawn with the web's one chart component (Recharts, §6.5).
import { SeriesChart, SeriesTable, type Unit } from "@/components/viz/SeriesChart";

export type DrawnChart = {
  name: string;
  type: string | null;
  categories: string[];
  series: { name: string; values: (number | null)[] }[];
  fmt?: string | null;
  highlight?: unknown;
};

const UNIT: Record<string, Unit> = { M: "SDR", k: "SDR", sdr: "SDR", "%1": "%", "%2": "%", d: "days" };

export function PackChart({ chart }: { chart: DrawnChart }) {
  if (!chart.categories.length || !chart.series.length) return null;
  const unit = UNIT[chart.fmt ?? ""] ?? null;
  const kind = (chart.type ?? "").includes("line") ? "line" : "bar";
  // the deck marks the report week on its trend line (render.py `highlight` = the category index): the preview too
  const hi =
    kind === "line" && typeof chart.highlight === "number" && chart.categories[chart.highlight] !== undefined
      ? chart.highlight
      : undefined;
  return (
    <div>
      <SeriesChart
        categories={chart.categories}
        series={chart.series}
        unit={unit}
        kind={kind}
        label={`${chart.name}: ${chart.series.map((s) => s.name).join(", ")}`}
        height={240}
        highlight={hi}
      />
      {hi !== undefined ? (
        <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="inline-block size-2.5 rounded-full bg-marker" aria-hidden />
          {chart.categories[hi]} is the report week.
        </p>
      ) : null}
      <SeriesTable categories={chart.categories} series={chart.series} unit={unit} />
    </div>
  );
}
