"use client";
// Arrival advice inside Voyages (Arrival advice web plan, ADR-070; owner 2026-11-17: the watch makes the advice).
// - `AdviceCard`: one advice — the recommended option (code's numbers), the written headline / reasons with their
//   receipts, every computed option, and "Compare routes" when the Cape is one of them. Used under a `jit` /
//   `rta_late` alert (the watch's own advice) and on an advice's page (`/voyages/arrival/<thread>`).
// - `ArrivalRequest`: ask for an advice for any vessel at sea, with an optional requested time (else the one the
//   port sent), then the earlier advice. POST /arrival-advice → the run's steps → the advice's page.
// The browser never computes a number: the options, times and fuel come from the API; it only formats them.
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Clock, Route as RouteIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import {
  listArrivalAdviceApiV1ArrivalAdviceGet as listAdvice,
  type ArrivalAdvice,
  type ArrivalOption,
} from "@/api/generated/client";
import { ReceiptText } from "@/components/receipt/ReceiptText";
import { Card, CardContent } from "@/components/ui/card";
import {
  arrivalThreadParts,
  formatHours,
  formatKn,
  formatSdrChange,
  formatTonnes,
  formatTonnesChange,
  OPTION_LABEL,
  STATUS_NOTE,
  stamp,
  summaryOf,
} from "@/lib/arrival-advice";
import { cn } from "@/lib/utils";

const WRITTEN = new Set(["ok", "computed"]);

function waitOrLate(o: ArrivalOption): string {
  if (typeof o.late_h === "number" && o.late_h > 0) return `${formatHours(o.late_h)} late`;
  if (o.arrives_by_rta === false) return "less than 0.1 h late";
  if (typeof o.wait_h === "number" && o.wait_h > 0) return `waits ${formatHours(o.wait_h)}`;
  return "on time";
}

function OptionsTable({ options, chosen }: { options: ArrivalOption[]; chosen: string | null }) {
  return (
    <div
      className="overflow-x-auto focus-visible:outline-2 focus-visible:outline-primary"
      tabIndex={0}
      role="region"
      aria-label="Speed options, scrolls sideways on small screens"
    >
      <table className="w-full min-w-[34rem] text-sm">
        <caption className="sr-only">Every speed option computed by code</caption>
        <thead>
          <tr className="text-xs text-muted-foreground">
            {["Option", "Speed", "Arrives", "Wait / late", "Fuel", "Fuel change", "Cost change"].map(
              (h, i) => (
                <th
                  key={h}
                  scope="col"
                  className={cn("py-1.5 font-medium", i < 4 ? "text-start" : "text-end")}
                >
                  {h}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {options.map((o) => (
            <tr
              key={o.option}
              className={cn("border-t", o.option === chosen ? "bg-accent font-medium" : "")}
              aria-current={o.option === chosen ? "true" : undefined}
            >
              <td className="py-2 pe-3">
                {OPTION_LABEL[o.option]}
                {o.option === chosen ? <span className="sr-only"> (recommended)</span> : null}
              </td>
              <td className="num py-2 pe-3">{o.speed_kn != null ? formatKn(o.speed_kn) : "—"}</td>
              <td className="py-2 pe-3 font-mono text-xs">{stamp(o.arrival_utc)}</td>
              <td className="py-2 pe-3 text-xs">{waitOrLate(o)}</td>
              <td className="num py-2 text-end">{o.fuel_t != null ? formatTonnes(o.fuel_t) : "—"}</td>
              <td className="num py-2 text-end">
                {o.change_fuel_t != null ? formatTonnesChange(o.change_fuel_t) : "—"}
              </td>
              <td className="num py-2 text-end">
                {o.change_total_sdr != null ? formatSdrChange(o.change_total_sdr) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** One advice. `compact` (under an alert): the recommendation line and a "Why and every option" disclosure. */
export function AdviceCard({ advice, compact = false }: { advice: ArrivalAdvice; compact?: boolean }) {
  const [open, setOpen] = useState(!compact);
  const s = summaryOf(advice.summary);
  const options = advice.options ?? [];
  const chosen = advice.recommendation ?? null;
  const pick = options.find((o) => o.option === chosen) ?? null;
  const numbers = advice.numbers ?? { headline: [], reasons: [], risks: [] };
  const written = WRITTEN.has(advice.status ?? "");
  const note =
    advice.status === "computed"
      ? "Calculated from this watch run’s speed options. Check the vessel’s active weather and traffic alerts before changing speed."
      : (STATUS_NOTE[advice.status ?? ""] ?? null);
  const differs = written && chosen && s.ruleOption && chosen !== s.ruleOption;
  const hasCape = options.some((o) => o.option === "cape");
  // the one line that matters (compact): the choice, its speed, when it arrives, the fuel it changes
  const lateDecision = advice.status === "computed" && s.situation === "late";
  let action = chosen ? OPTION_LABEL[chosen] : "Computed options only";
  if (lateDecision && chosen === "keep") action = "Notify the port of the delay";
  if (advice.status === "review") action = "Confirm the arrival window";
  const keyLine = (
    <p className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5 text-sm">
      <Clock className="size-4 shrink-0 text-primary" aria-hidden />
      <span className="font-semibold text-primary">{action}</span>
      {pick?.speed_kn != null ? <span className="num font-medium">{formatKn(pick.speed_kn)}</span> : null}
      {pick ? (
        <span className="text-xs text-muted-foreground">
          arrives <bdi className="font-mono">{stamp(pick.arrival_utc)}</bdi>
          {pick.change_fuel_t != null && pick.change_fuel_t !== 0 ? (
            <>
              {" "}
              · fuel{" "}
              <span className="num font-semibold text-foreground">
                {formatTonnesChange(pick.change_fuel_t)}
              </span>
            </>
          ) : null}
        </span>
      ) : null}
    </p>
  );
  return (
    <div
      className={cn(
        "flex flex-col gap-2 rounded-md bg-accent/50",
        compact ? "px-3 py-2" : "border-s-4 border-primary p-4",
      )}
      aria-label="Arrival advice"
      role="group"
    >
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">{keyLine}</div>
        {compact ? (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="flex shrink-0 items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            Details
            <ChevronDown
              className={cn("size-3.5 transition-transform", open ? "rotate-180" : "")}
              aria-hidden
            />
          </button>
        ) : null}
      </div>
      {compact && !open && advice.status === "computed" && advice.headline ? (
        <p className="text-sm" dir="auto">
          {advice.headline}
        </p>
      ) : null}
      {open ? (
        <div className="flex flex-col gap-3">
          {pick ? (
            <p className="text-xs text-muted-foreground">{waitOrLate(pick)} at its destination.</p>
          ) : null}
          {s.rtaUtc ? (
            <p className="text-xs text-muted-foreground">
              Requested time <bdi className="font-mono">{stamp(s.rtaUtc)}</bdi> at the{" "}
              {(s.location ?? "berth").replaceAll("_", " ")}
              {s.destination ? (
                <>
                  {" "}
                  of <bdi className="font-mono font-semibold text-foreground">{s.destination}</bdi>
                </>
              ) : null}
              {s.rtaSource ? <> ({s.rtaSource.replaceAll("_", " ")})</> : null}
            </p>
          ) : null}
          {advice.headline ? (
            <p dir="auto" className="text-sm">
              <ReceiptText text={advice.headline} numbers={numbers.headline ?? []} />
            </p>
          ) : null}
          {note ? (
            <p role="status" className="text-xs text-muted-foreground">
              {note}
            </p>
          ) : null}
          {differs ? (
            <p className="text-xs text-waiting-ink">
              The rule alone would choose “
              {OPTION_LABEL[s.ruleOption as ArrivalOption["option"]] ?? s.ruleOption}”; the advice departs
              from it for the risk named first below.
            </p>
          ) : null}
          {advice.reasons?.length ? (
            <ul className="flex list-disc flex-col gap-1 ps-5 text-sm" aria-label="Reasons">
              {advice.reasons.map((r, i) => (
                <li key={i} dir="auto">
                  <ReceiptText text={r} numbers={numbers.reasons?.[i] ?? []} />
                </li>
              ))}
            </ul>
          ) : null}
          {advice.risks?.length ? (
            <ul className="flex flex-col gap-1 text-sm text-waiting-ink" aria-label="Risks">
              {advice.risks.map((r, i) => (
                <li key={i} dir="auto">
                  <ReceiptText text={r} numbers={numbers.risks?.[i] ?? []} />
                </li>
              ))}
            </ul>
          ) : null}
          {options.length ? <OptionsTable options={options} chosen={chosen} /> : null}
          {advice.assumptions?.length ? (
            <ul className="flex flex-col gap-0.5 text-xs text-muted-foreground" aria-label="Assumptions">
              {advice.assumptions.map((a, i) => (
                <li key={i} dir="auto">
                  {a}
                </li>
              ))}
            </ul>
          ) : null}
          {advice.status === "error" && advice.problems?.length ? (
            <p className="text-xs text-muted-foreground" dir="auto">
              {advice.problems[0]}
            </p>
          ) : null}
          {hasCape && s.vesselId != null ? (
            <Link
              href={`/routes?vessel=${s.vesselId}${s.destination ? `&destination=${s.destination}` : ""}`}
              className="flex w-fit items-center gap-1.5 text-sm font-medium text-primary hover:underline"
            >
              <RouteIcon className="size-4" aria-hidden /> Compare routes for this vessel
            </Link>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** "YYYY-MM-DDTHH:MM" typed in UTC → the API's ISO with Z; empty = the RTA the port sent. */
export function ArrivalHistory() {
  const earlier = useQuery({ queryKey: ["arrival-advice"], queryFn: () => listAdvice(), retry: false });
  const rows = [...(earlier.data ?? [])].sort((a, b) => b.last_at.localeCompare(a.last_at)).slice(0, 12);
  return (
    <Card>
      <CardContent>
        <div className="flex flex-col gap-1.5">
          <p className="text-xs font-medium">Earlier advice</p>
          <ul className="flex flex-col gap-1.5" aria-label="Earlier arrival advice">
            {rows.map((r) => {
              const p = arrivalThreadParts(r.thread_id);
              return (
                <li key={r.thread_id}>
                  <Link
                    href={`/voyages/arrival/${encodeURIComponent(r.thread_id)}`}
                    className="flex items-center gap-2 rounded-lg border px-3 py-2 text-xs hover:border-primary"
                  >
                    <span className="font-mono font-semibold">
                      {p ? `Vessel ${p.vessel} · ${p.date} · #${p.n}` : r.thread_id}
                    </span>
                    <span className="ms-auto text-muted-foreground">
                      {(r.status ?? r.state).replaceAll("_", " ")}
                    </span>
                  </Link>
                </li>
              );
            })}
            {!earlier.isPending && rows.length === 0 ? (
              <li className="text-xs text-muted-foreground">None yet.</li>
            ) : null}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}
