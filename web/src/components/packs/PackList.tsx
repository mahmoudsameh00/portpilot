"use client";
// The packs list and the approval report (plan §6.4).
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BarChart3, Loader2 } from "lucide-react";
import Link from "next/link";
import {
  listPacksApiV1PacksGet as listPacks,
  reportApiV1PacksReportGet as getReport,
} from "@/api/generated/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const STATE: Record<string, { label: string; tone: string }> = {
  pending: { label: "Waiting for a decision", tone: "bg-waiting-wash text-waiting-ink" },
  ended: { label: "Ended", tone: "bg-muted text-muted-foreground" },
  stalled: { label: "Stopped mid-run", tone: "bg-alert-wash text-alert-ink" },
};

export function PackList({ canDecide }: { canDecide: boolean }) {
  const { data, isPending, error } = useQuery({ queryKey: ["packs"], queryFn: () => listPacks() });
  const rows = [...(data ?? [])].sort((a, b) => b.week - a.week || b.attempt - a.attempt);
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end gap-3">
        <div className="me-auto">
          <h1 className="text-2xl font-semibold">Weekly finance packs</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Drafted on Monday, checked by code, decided by a manager.
          </p>
        </div>
        {canDecide ? (
          <Link
            href="/packs/report"
            className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
          >
            <BarChart3 className="size-4" aria-hidden /> Approval report
          </Link>
        ) : null}
      </div>
      {isPending ? <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden /> : null}
      {error ? (
        <p role="alert" className="text-sm text-alert-ink">
          The packs could not be loaded.
        </p>
      ) : null}
      <ul className="flex flex-col gap-2">
        {rows.map((p) => {
          const st = STATE[p.state] ?? { label: p.state, tone: "bg-muted text-muted-foreground" };
          return (
            <li key={p.thread_id}>
              <Link
                href={`/packs/${encodeURIComponent(p.thread_id)}`}
                className="flex flex-wrap items-center gap-4 rounded-xl border bg-card px-5 py-4 transition-colors hover:border-primary"
              >
                <span className="font-mono text-lg font-semibold">
                  2025-W{String(p.week).padStart(2, "0")}
                </span>
                <span className="text-xs text-muted-foreground">attempt {p.attempt}</span>
                <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-semibold", st.tone)}>
                  {st.label}
                </span>
                {p.status ? (
                  <span className="text-xs text-muted-foreground">{p.status.replaceAll("_", " ")}</span>
                ) : null}
                <ArrowRight className="ms-auto size-4 text-muted-foreground" aria-hidden />
              </Link>
            </li>
          );
        })}
        {!isPending && !error && rows.length === 0 ? (
          <li className="text-sm text-muted-foreground">
            No pack yet. The next one is drafted on Monday at 10:30.
          </li>
        ) : null}
      </ul>
    </div>
  );
}

export function PackReport() {
  const { data, isPending, error } = useQuery({ queryKey: ["pack-report"], queryFn: () => getReport() });
  if (isPending) return <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden />;
  if (error || !data)
    return (
      <p role="alert" className="text-sm text-alert-ink">
        The report could not be loaded.
      </p>
    );
  const tiles = [
    { label: "Packs decided", value: data.packs_decided },
    { label: "Published", value: data.published },
    { label: "Rejected", value: data.rejected },
    {
      label: "Edited before approval",
      value: data.edit_rate === null ? "—" : `${Math.round(data.edit_rate * 100)}%`,
    },
  ];
  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-2xl font-semibold">Approval report</h1>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {tiles.map((t) => (
          <Card key={t.label} className="gap-1 py-4">
            <CardHeader className="px-4">
              <CardDescription>{t.label}</CardDescription>
              <CardTitle className="num text-2xl">{t.value}</CardTitle>
            </CardHeader>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Changes made by approvers</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
            {Object.entries(data.changes).map(([k, v]) => (
              <li key={k} className="flex justify-between rounded-md bg-muted px-3 py-2">
                <span className="text-muted-foreground">{k.replaceAll("_", " ")}</span>
                <span className="num font-semibold">{v}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
