"use client";
// The voyage watch (plan §6.0 (8), §6.7): the radar list of the latest (or one) run's alerts from
// GET /voyage-watch/alerts (filter high / all, kept in the URL), the run's brief and fleet counts from
// GET /voyage-watch/runs/{thread} (headline + items with their number receipts), and the runs list. Read only:
// Task Scheduler starts the runs. The API decides who reads what (`not_permitted` is an answer, not an error).
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  CloudLightning,
  Cpu,
  Loader2,
  Radar as RadarIcon,
  Ship,
  Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  watchAlertsApiV1VoyageWatchAlertsGet as getAlerts,
  watchRunApiV1VoyageWatchRunsThreadIdGet as getRun,
  watchRunsApiV1VoyageWatchRunsGet as listRuns,
  type WatchAlert,
  type WatchEta,
  type WatchRunDetail,
} from "@/api/generated/client";
import { ReceiptText } from "@/components/receipt/ReceiptText";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Radar, type Blip } from "@/components/viz/charts";
import { BffError } from "@/lib/bff/client";
import { cn } from "@/lib/utils";

const SEVERITY: Record<string, { label: string; tone: string; level: Blip["level"]; ring: number }> = {
  high: { label: "High", tone: "bg-alert-wash text-alert-ink", level: "high", ring: 0.38 },
  moderate: { label: "Moderate", tone: "bg-waiting-wash text-waiting-ink", level: "medium", ring: 0.66 },
};
const LOW = { label: "Low", tone: "bg-muted text-muted-foreground", level: "low" as const, ring: 0.9 };

const KIND: Record<string, { label: string; icon: typeof Ship }> = {
  weather: { label: "Weather", icon: CloudLightning },
  suez_traffic: { label: "Suez traffic", icon: Ship },
  customer: { label: "Customer", icon: Users },
};

const FLEET: { key: string; label: string; format?: (v: number) => string }[] = [
  { key: "vessels_watched", label: "Vessels watched" },
  { key: "in_transit", label: "In transit" },
  { key: "anchored", label: "Anchored" },
  { key: "alerts_high", label: "High alerts" },
  { key: "alerts_moderate", label: "Moderate alerts" },
  { key: "suez_ahead_vessels", label: "Suez ahead" },
  { key: "weather_points", label: "Weather points read" },
  {
    key: "change_transits_pct",
    label: "Suez transits vs a year ago",
    format: (v) =>
      `${new Intl.NumberFormat("en", { signDisplay: "exceptZero", maximumFractionDigits: 1 }).format(v)}%`,
  },
];

const stamp = (iso: string | null | undefined) => (iso ? iso.replace("T", " ") : "—");
const runParts = (thread: string) => {
  const m = /^voyage_watch:(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})Z:(\d+)$/.exec(thread);
  return m ? `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}Z · run ${m[6]}` : thread;
};

/** Where a blip sits: the ring by severity, the angle by its place in the list (a layout, not a value). */
function blipsOf(alerts: WatchAlert[]): Blip[] {
  return alerts.slice(0, 40).map((a, i) => {
    const sev = SEVERITY[a.severity ?? ""] ?? LOW;
    return {
      vessel: a.vessel_name ?? a.alert_id,
      text: a.reason ?? KIND[a.kind]?.label ?? a.kind,
      level: sev.level,
      angle: (i * 137.5) % 360,
      dist: sev.ring + ((i % 3) - 1) * 0.06,
    };
  });
}

function AlertRow({ a }: { a: WatchAlert }) {
  const sev = SEVERITY[a.severity ?? ""] ?? LOW;
  const kind = KIND[a.kind] ?? { label: a.kind, icon: AlertTriangle };
  const Icon = kind.icon;
  return (
    <li className="grid gap-x-4 gap-y-1 rounded-lg border bg-card px-4 py-3 sm:grid-cols-[6.5rem_minmax(0,1fr)_auto]">
      <span
        className={cn(
          "inline-flex h-6 w-fit items-center gap-1 rounded-full px-2.5 text-xs font-semibold",
          sev.tone,
        )}
      >
        {a.severity === "high" ? <AlertTriangle className="size-3.5" aria-hidden /> : null}
        {sev.label}
      </span>
      <div className="min-w-0">
        <p className="flex flex-wrap items-center gap-x-2 text-sm font-medium">
          <span>{a.vessel_name ?? `Vessel ${a.vessel_id ?? "—"}`}</span>
          <span className="inline-flex items-center gap-1 rounded-md bg-accent px-1.5 py-0.5 text-xs font-normal">
            <Icon className="size-3.5" aria-hidden /> {kind.label}
          </span>
        </p>
        {a.reason ? (
          <p dir="auto" className="mt-0.5 text-sm text-muted-foreground">
            {a.reason}
          </p>
        ) : null}
      </div>
      <p className="text-xs text-muted-foreground sm:text-end">
        {a.destination ? (
          <>
            to <bdi className="font-mono font-semibold text-foreground">{a.destination}</bdi>
            <br />
          </>
        ) : null}
        ETA <bdi className="font-mono">{stamp(a.eta_utc)}</bdi>
      </p>
    </li>
  );
}

function RunBrief({ run }: { run: WatchRunDetail }) {
  const numbers = run.numbers ?? { headline: [], items: [] };
  const fleet = run.fleet ?? {};
  return (
    <div className="flex flex-col gap-4">
      {run.headline ? (
        <p dir="auto" className="text-lg leading-relaxed font-medium">
          <ReceiptText text={run.headline} numbers={numbers.headline ?? []} />
        </p>
      ) : (
        <p className="text-sm text-muted-foreground">
          No written brief for this run ({(run.brief_status ?? "none").replaceAll("_", " ")}); the alerts
          below are the code&apos;s own.
        </p>
      )}
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4" aria-label="Fleet at the run's clock">
        {FLEET.map((f) => {
          const v = fleet[f.key];
          return (
            <div key={f.key} className="rounded-lg bg-muted px-3 py-2">
              <dt className="text-xs text-muted-foreground">{f.label}</dt>
              <dd className="num text-lg font-semibold" data-field={f.key}>
                {typeof v === "number"
                  ? f.format
                    ? f.format(v)
                    : new Intl.NumberFormat("en").format(v)
                  : "—"}
              </dd>
            </div>
          );
        })}
      </dl>
      {run.items?.length ? (
        <ul className="flex flex-col gap-2" aria-label="The brief">
          {run.items.map((t, i) => (
            <li key={i} dir="auto" className="rounded-lg border bg-card px-4 py-3 text-sm leading-relaxed">
              <ReceiptText text={t} numbers={numbers.items?.[i] ?? []} />
            </li>
          ))}
        </ul>
      ) : null}
      <details className="group border-t pt-3">
        <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium">
          <ChevronDown className="size-4 transition-transform group-open:rotate-180" aria-hidden /> How we
          know
          <span className="ms-auto flex items-center gap-1 text-xs font-normal text-muted-foreground">
            <Cpu className="size-3.5" aria-hidden /> {run.model_calls ?? 0} model calls
          </span>
        </summary>
        <div className="mt-3 grid gap-4 text-sm md:grid-cols-2">
          {run.assumptions?.length ? (
            <div>
              <h4 className="mb-1 text-xs font-semibold text-muted-foreground">Assumptions</h4>
              <ul className="flex list-disc flex-col gap-1 ps-5">
                {run.assumptions.map((a, i) => (
                  <li key={i} dir="auto">
                    {a}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <div>
            <h4 className="mb-1 text-xs font-semibold text-muted-foreground">Run</h4>
            <p className="font-mono text-xs break-words">{run.thread_id}</p>
            {run.run_file ? <p className="mt-1 font-mono text-xs break-words">{run.run_file}</p> : null}
          </div>
          {run.problems?.length ? (
            <div className="md:col-span-2">
              <h4 className="mb-1 text-xs font-semibold text-muted-foreground">
                Problems found by the checks
              </h4>
              <ul className="flex list-disc flex-col gap-1 ps-5">
                {run.problems.map((p, i) => (
                  <li key={i} dir="auto">
                    {p}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </details>
    </div>
  );
}

const nf = (digits: number) =>
  new Intl.NumberFormat("en", { minimumFractionDigits: digits, maximumFractionDigits: digits });

/** The run's ETA table (rule R at the run's clock; never the schedule's arrival — ADR-055): vessels at sea, soonest
 * first, the vessels with alerts marked. The bar is a visual scale of the API's `eta_in_h`; the numbers are shown. */
function EtaBoard({ etas, alerted }: { etas: WatchEta[]; alerted: Set<number> }) {
  const [all, setAll] = useState(false);
  const atSea = etas
    .filter((e) => typeof e.eta_in_h === "number")
    .sort((a, b) => (a.eta_in_h ?? 0) - (b.eta_in_h ?? 0));
  const rows = all
    ? atSea
    : [
        ...atSea.filter((e) => alerted.has(e.vessel_id)),
        ...atSea.filter((e) => !alerted.has(e.vessel_id)),
      ].slice(0, 12);
  const longest = Math.max(1, ...atSea.map((e) => e.eta_in_h ?? 0));
  if (!atSea.length) return <p className="text-sm text-muted-foreground">No vessel at sea in this run.</p>;
  return (
    <div className="flex flex-col gap-3">
      <div
        className="overflow-x-auto focus-visible:outline-2 focus-visible:outline-primary"
        tabIndex={0}
        role="region"
        aria-label="ETA board, scrolls sideways on small screens"
      >
        <table className="w-full min-w-[34rem] text-sm">
          <caption className="sr-only">ETA by rule for the vessels at sea</caption>
          <thead>
            <tr className="text-start text-xs text-muted-foreground">
              <th scope="col" className="py-1.5 text-start font-medium">
                Vessel
              </th>
              <th scope="col" className="py-1.5 text-start font-medium">
                Next port → destination
              </th>
              <th scope="col" className="py-1.5 text-start font-medium">
                ETA (rule)
              </th>
              <th scope="col" className="w-40 py-1.5 text-start font-medium">
                Hours to go
              </th>
              <th scope="col" className="py-1.5 text-end font-medium">
                Left · speed
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.vessel_id} className="border-t">
                <td className="py-2 pe-3">
                  <span className="font-medium">{e.vessel_name ?? `Vessel ${e.vessel_id}`}</span>
                  {alerted.has(e.vessel_id) ? (
                    <span className="ms-2 rounded-full bg-alert-wash px-1.5 py-0.5 text-[11px] font-semibold text-alert-ink">
                      alert
                    </span>
                  ) : null}
                  {e.suez_ahead ? (
                    <span className="ms-1.5 rounded-full bg-accent px-1.5 py-0.5 text-[11px]">
                      Suez ahead
                    </span>
                  ) : null}
                </td>
                <td className="py-2 pe-3 font-mono text-xs">
                  <bdi>{e.next_port ?? "—"}</bdi> →{" "}
                  <bdi className="font-semibold">{e.destination ?? "—"}</bdi>
                </td>
                <td className="py-2 pe-3 font-mono text-xs">{stamp(e.eta_utc)}</td>
                <td className="py-2 pe-3">
                  <span className="flex items-center gap-2">
                    <span className="h-1.5 flex-1 rounded-full bg-muted" aria-hidden>
                      <span
                        className={cn(
                          "block h-1.5 rounded-full",
                          alerted.has(e.vessel_id) ? "bg-alert" : "bg-chart-1",
                        )}
                        style={{ width: `${((e.eta_in_h ?? 0) / longest) * 100}%` }}
                      />
                    </span>
                    <span
                      className="num w-14 text-end text-xs"
                      data-field="eta_in_h"
                      data-value={e.eta_in_h ?? ""}
                    >
                      {nf(1).format(e.eta_in_h ?? 0)} h
                    </span>
                  </span>
                </td>
                <td className="num py-2 text-end text-xs text-muted-foreground">
                  {e.distance_left_nm != null ? `${nf(0).format(e.distance_left_nm)} nm` : "—"} ·{" "}
                  {e.speed_kn != null ? `${nf(1).format(e.speed_kn)} kn` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span>
          ETA by rule: the distance left at the vessel&apos;s recent speed, at the run&apos;s clock — never
          the schedule.
        </span>
        {atSea.length > 12 ? (
          <button
            type="button"
            onClick={() => setAll((v) => !v)}
            className="ms-auto font-medium text-primary hover:underline"
            aria-expanded={all}
          >
            {all ? "Show the first 12" : `Show all ${atSea.length} vessels at sea`}
          </button>
        ) : null}
      </div>
    </div>
  );
}

function Runs({ current }: { current: string | null }) {
  const { data, isPending, error } = useQuery({
    queryKey: ["watch-runs"],
    queryFn: () => listRuns(),
    retry: false,
  });
  const rows = [...(data ?? [])].sort((a, b) => b.thread_id.localeCompare(a.thread_id)).slice(0, 20);
  return (
    <Card className="gap-3">
      <CardHeader>
        <CardTitle className="text-base">Watch runs</CardTitle>
      </CardHeader>
      <CardContent>
        {isPending ? <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden /> : null}
        {error ? (
          <p className="text-sm text-muted-foreground">The runs list is not available to you.</p>
        ) : null}
        <ul className="flex flex-col gap-1.5" aria-label="Watch runs">
          {rows.map((r) => (
            <li key={r.thread_id}>
              <Link
                href={`/voyages/runs/${encodeURIComponent(r.thread_id)}`}
                aria-current={r.thread_id === current ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 rounded-lg border px-3 py-2 text-xs transition-colors hover:border-primary",
                  r.thread_id === current ? "border-primary bg-accent" : "",
                )}
              >
                <span className="font-mono font-semibold">{runParts(r.thread_id)}</span>
                <span className="ms-auto text-muted-foreground">
                  {(r.status ?? r.state).replaceAll("_", " ")}
                </span>
              </Link>
            </li>
          ))}
          {!isPending && !error && rows.length === 0 ? (
            <li className="text-sm text-muted-foreground">No run yet. The watch runs at 10:30 and 22:30.</li>
          ) : null}
        </ul>
      </CardContent>
    </Card>
  );
}

export function VoyageWatch({ thread }: { thread?: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const high = params.get("high") === "1";
  const alerts = useQuery({
    queryKey: ["watch-alerts", thread ?? null, high],
    queryFn: () => getAlerts({ ...(thread ? { thread } : {}), ...(high ? { high: true } : {}) }),
    retry: false,
  });
  const runThread = thread ?? (alerts.data?.status === "ok" ? (alerts.data.thread_id ?? null) : null);
  const run = useQuery({
    queryKey: ["watch-run", runThread],
    queryFn: () => getRun(runThread!),
    enabled: Boolean(runThread),
    retry: false,
  });
  const setHigh = (next: boolean) => {
    const q = new URLSearchParams(params.toString());
    if (next) q.set("high", "1");
    else q.delete("high");
    router.replace(`${pathname}${q.size ? `?${q}` : ""}`, { scroll: false });
  };
  const a = alerts.data;
  const list = a?.status === "ok" ? (a.alerts ?? []) : [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end gap-3">
        <div className="me-auto">
          <h1 className="flex items-center gap-2 text-2xl font-semibold">
            <RadarIcon className="size-6 text-primary" aria-hidden /> Voyage watch
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {thread ? <>Run {runParts(thread)}. </> : null}
            Every vessel at sea checked by fixed rules every 12 hours (10:30 and 22:30); the brief is written
            from the alerts.
          </p>
        </div>
        {thread ? (
          <Link href="/voyages" className="text-sm font-medium text-primary hover:underline">
            Latest run
          </Link>
        ) : null}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-w-0 flex-col gap-6">
          <Card>
            <CardHeader className="flex flex-row flex-wrap items-center gap-3">
              <CardTitle className="me-auto text-base">Alerts</CardTitle>
              <div className="flex gap-1.5" role="group" aria-label="Filter alerts">
                {(
                  [
                    [true, "High only"],
                    [false, "All"],
                  ] as const
                ).map(([value, label]) => (
                  <button
                    key={label}
                    type="button"
                    aria-pressed={high === value}
                    onClick={() => setHigh(value)}
                    className={cn(
                      "h-8 rounded-full border px-3 text-sm transition-colors",
                      high === value ? "border-primary bg-accent font-medium" : "hover:border-primary",
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </CardHeader>
            <CardContent>
              {alerts.isPending ? (
                <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden />
              ) : null}
              {alerts.error ? (
                <p role="alert" className="text-sm text-alert-ink">
                  {alerts.error instanceof BffError && alerts.error.status === 404
                    ? "This run is not on the chart."
                    : "The alerts could not be loaded."}
                </p>
              ) : null}
              {a && a.status !== "ok" ? (
                <p role="status" className="rounded-lg bg-muted px-4 py-3 text-sm text-muted-foreground">
                  {a.status === "not_permitted"
                    ? "The voyage watch is not part of your access."
                    : "No saved watch run yet. The first one arrives at the next 10:30 or 22:30 run."}
                </p>
              ) : null}
              {a?.status === "ok" ? (
                <div className="grid gap-5 md:grid-cols-[13rem_minmax(0,1fr)]">
                  <div className="mx-auto aspect-square w-52 md:w-full">
                    <Radar blips={blipsOf(list)} />
                  </div>
                  <div className="flex min-w-0 flex-col gap-3">
                    <p className="text-xs text-muted-foreground" aria-live="polite">
                      Showing <span className="num font-semibold text-foreground">{list.length}</span> of{" "}
                      <span className="num">{a.of ?? list.length}</span> alerts · clock{" "}
                      <bdi className="font-mono">{stamp(a.as_of)}</bdi>
                    </p>
                    <ul className="flex flex-col gap-2" aria-label="Alerts by severity">
                      {list.map((x) => (
                        <AlertRow key={x.alert_id} a={x} />
                      ))}
                      {list.length === 0 ? (
                        <li className="text-sm text-muted-foreground">
                          {high ? "No high alert in this run." : "No alert in this run."}
                        </li>
                      ) : null}
                    </ul>
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>

          {runThread ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">The run&apos;s brief</CardTitle>
              </CardHeader>
              <CardContent>
                {run.isPending ? (
                  <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden />
                ) : null}
                {run.error ? (
                  <p className="text-sm text-muted-foreground">
                    The run&apos;s brief is not available to you.
                  </p>
                ) : null}
                {run.data ? <RunBrief run={run.data} /> : null}
              </CardContent>
            </Card>
          ) : null}
          {run.data?.etas?.length ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">ETA board</CardTitle>
              </CardHeader>
              <CardContent>
                <EtaBoard
                  etas={run.data.etas}
                  alerted={
                    new Set(list.map((x) => x.vessel_id).filter((v): v is number => typeof v === "number"))
                  }
                />
              </CardContent>
            </Card>
          ) : null}
        </div>
        <Runs current={runThread} />
      </div>
    </div>
  );
}
