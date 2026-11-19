// One dashboard figure = one card with its own Download (web dashboards plan amendment 1, D-WD-6, owner 2026-11-15):
// the API builds the file from the figure's own rows exactly as the view gives them, with its source view and filter
// (GET /finance/export/figure — a one-sheet workbook + About, or CSV), checks the same access rule as the dashboard
// and writes one audit row per download. The browser only builds the link.
import { Download } from "lucide-react";
import type { ReactNode } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export type FigureRef = {
  figure:
    | "kpis"
    | "trend"
    | "category"
    | "overdue"
    | "customers"
    | "breakdown"
    | "audit_summary"
    | "audit_findings";
  week: number;
  page?: string;
  dimension?: string;
  compare?: number | null;
  ytd?: boolean;
  limit?: number;
};

export function figureHref(ref: FigureRef, format: "xlsx" | "csv"): string {
  const q = new URLSearchParams({ week: String(ref.week), figure: ref.figure, format });
  if (ref.page) q.set("page", ref.page);
  if (ref.dimension) q.set("dimension", ref.dimension);
  if (ref.compare) q.set("compare", String(ref.compare));
  if (ref.ytd) q.set("ytd", "true");
  if (ref.limit) q.set("limit", String(ref.limit));
  return `/bff/finance/export/figure?${q.toString()}`;
}

const linkClass =
  "inline-flex h-8 items-center gap-1.5 rounded-md border px-2.5 text-xs font-medium text-primary hover:bg-accent";

/** "Download: Excel · CSV" for one figure; the accessible names say which figure. */
export function FigureDownload({ name, of }: { name: string; of: FigureRef }) {
  return (
    <div role="group" aria-label={`Download ${name}`} className="flex shrink-0 items-center gap-1.5">
      <Download className="size-3.5 text-muted-foreground" aria-hidden />
      <a
        href={figureHref(of, "xlsx")}
        download
        className={linkClass}
        aria-label={`Download ${name} as Excel`}
      >
        Excel
      </a>
      <a href={figureHref(of, "csv")} download className={linkClass} aria-label={`Download ${name} as CSV`}>
        CSV
      </a>
    </div>
  );
}

export function FigureCard({
  title,
  source,
  of,
  controls,
  children,
  className,
  label,
}: {
  title: ReactNode;
  /** the view and filter, shown under the title */
  source?: string;
  /** what the Download exports; none = no Download */
  of?: FigureRef;
  controls?: ReactNode;
  children: ReactNode;
  className?: string;
  /** the card's accessible name (defaults to the title when it is text) */
  label?: string;
}) {
  const name = label ?? (typeof title === "string" ? title : "this figure");
  return (
    <Card aria-label={name} className={cn(className)}>
      <CardHeader>
        <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
          <div className="me-auto min-w-0">
            <CardTitle className="text-base">{title}</CardTitle>
            {source ? (
              <CardDescription className="mt-1 font-mono text-xs break-all">{source}</CardDescription>
            ) : null}
          </div>
          {of ? <FigureDownload name={name} of={of} /> : null}
        </div>
        {controls}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}
