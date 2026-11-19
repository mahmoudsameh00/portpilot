"use client";
// Arrival advice inside Voyages (Arrival advice web plan, ADR-070; owner 2026-11-17: the watch makes the advice).
// - `AdviceCard`: one advice — the recommended option (code's numbers), the written headline / reasons with their
//   receipts, every computed option, and "Compare routes" when the Cape is one of them. Used under a `jit` /
//   `rta_late` alert (the watch's own advice) and on an advice's page (`/voyages/arrival/<thread>`).
// - `ArrivalRequest`: ask for an advice for any vessel at sea, with an optional requested time (else the one the
//   port sent), then the earlier advice. POST /arrival-advice → the run's steps → the advice's page.
// The browser never computes a number: the options, times and fuel come from the API; it only formats them.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Anchor, ChevronDown, Clock, Loader2, Route as RouteIcon } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  arrivalAdviceApiV1ArrivalAdvicePost as postAdvice,
  listArrivalAdviceApiV1ArrivalAdviceGet as listAdvice,
  type ArrivalAdvice,
  type ArrivalIn,
  type ArrivalOption,
  type RunEventSchema,
} from "@/api/generated/client";
import { ReceiptText } from "@/components/receipt/ReceiptText";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ARRIVAL_STEPS,
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
import { BffError } from "@/lib/bff/client";
import { RunObservationError, streamRun } from "@/lib/runs";
import { cn } from "@/lib/utils";

const WRITTEN = new Set(["ok"]);

function waitOrLate(o: ArrivalOption): string {
  if (typeof o.late_h === "number" && o.late_h > 0) return `${formatHours(o.late_h)} late`;
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
  const note = written ? null : (STATUS_NOTE[advice.status ?? ""] ?? null);
  const differs = written && chosen && s.ruleOption && chosen !== s.ruleOption;
  const hasCape = options.some((o) => o.option === "cape");
  // the one line that matters (compact): the choice, its speed, when it arrives, the fuel it changes
  const keyLine = (
    <p className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5 text-sm">
      <Clock className="size-4 shrink-0 text-primary" aria-hidden />
      <span className="font-semibold text-primary">
        {pick ? OPTION_LABEL[pick.option] : chosen ? OPTION_LABEL[chosen] : "Computed options only"}
      </span>
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
function rtaOf(local: string): string | null {
  return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(local) ? `${local}:00Z` : null;
}

export function ArrivalRequest() {
  const router = useRouter();
  const qc = useQueryClient();
  const params = useSearchParams();
  const [vessel, setVessel] = useState(params.get("advise") ?? "");
  const [rta, setRta] = useState("");
  const [location, setLocation] = useState<"berth" | "pilot_boarding_place">("berth");
  const [busy, setBusy] = useState(false);
  const [seen, setSeen] = useState<Set<string>>(new Set());
  const [message, setMessage] = useState<string | null>(null);
  const earlier = useQuery({ queryKey: ["arrival-advice"], queryFn: () => listAdvice(), retry: false });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const id = Number(vessel);
    if (!Number.isInteger(id) || id < 1) {
      setMessage("Give the id of one of our vessels at sea.");
      return;
    }
    if (rta && !rtaOf(rta)) {
      setMessage("Give the requested time as date and time (UTC), or leave it empty.");
      return;
    }
    const body: ArrivalIn = { vessel_id: id, location, ...(rta ? { rta_utc: rtaOf(rta) } : {}) };
    setBusy(true);
    setSeen(new Set());
    setMessage(null);
    try {
      const accepted = await postAdvice(body);
      let failed: string | null = null;
      await streamRun(accepted.run_id, {
        onEvent: (ev: RunEventSchema) => {
          if (ev.event === "node" && ev.data.phase === "start") setSeen((s) => new Set([...s, ev.data.name]));
          if (ev.event === "failed") failed = ev.data.detail;
        },
      });
      if (failed) {
        setMessage(failed);
        return;
      }
      await qc.invalidateQueries({ queryKey: ["arrival-advice"] });
      if (accepted.thread_id) router.push(`/voyages/arrival/${encodeURIComponent(accepted.thread_id)}`);
    } catch (error) {
      setMessage(
        error instanceof RunObservationError
          ? error.message
          : error instanceof BffError
            ? error.status === 403
              ? "Arrival advice is not part of your access."
              : error.title
            : "The advice could not be asked for. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  const rows = [...(earlier.data ?? [])].sort((a, b) => b.thread_id.localeCompare(a.thread_id)).slice(0, 12);
  return (
    <Card className="gap-3" id="arrival">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Anchor className="size-4 text-primary" aria-hidden /> Arrival advice
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-xs text-muted-foreground">
          Which speed makes the port&apos;s requested time: keep and wait, slow down, or speed up — priced by
          code, then explained.
        </p>
        <form onSubmit={submit} className="flex flex-col gap-3" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="arrival-vessel">Vessel id</Label>
            <Input
              id="arrival-vessel"
              inputMode="numeric"
              className="h-9 font-mono"
              value={vessel}
              onChange={(e) => setVessel(e.target.value.replace(/\D/g, ""))}
              autoComplete="off"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="arrival-rta">Requested time (UTC, optional)</Label>
            <Input
              id="arrival-rta"
              type="datetime-local"
              className="h-9 font-mono"
              value={rta}
              onChange={(e) => setRta(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="arrival-location">Where it applies</Label>
            <select
              id="arrival-location"
              className="h-9 rounded-md border bg-background px-2 text-sm"
              value={location}
              onChange={(e) => setLocation(e.target.value as typeof location)}
            >
              <option value="berth">Berth</option>
              <option value="pilot_boarding_place">Pilot boarding place</option>
            </select>
          </div>
          <Button type="submit" disabled={busy}>
            {busy ? <Loader2 className="animate-spin" aria-hidden /> : null} Advise arrival
          </Button>
        </form>
        {busy || seen.size ? (
          <ol className="flex flex-col gap-1 text-xs" aria-label="What is being done">
            {ARRIVAL_STEPS.filter((s) => seen.has(s.node)).map((s) => (
              <li key={s.node} className="text-muted-foreground">
                {s.label}
              </li>
            ))}
          </ol>
        ) : null}
        {message ? (
          <p role="alert" className="text-sm text-alert-ink">
            {message}
          </p>
        ) : null}
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
