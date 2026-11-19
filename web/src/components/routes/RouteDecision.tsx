"use client";
// One route advice as a decision (plan §6.0 (7), §6.6): Suez | Cape side by side from `comparison`, the recommended
// card badged, the difference line from the graph's own `route.difference`, then the headline, reasons and risks with
// their number receipts (`numbers`), and "How we know" (assumptions, sources, problems, model calls).
// Model text is plain text with dir="auto"; numbers are the API's — the browser only formats them.
import { AlertTriangle, ChevronDown, Cpu, Receipt, ShieldCheck } from "lucide-react";
import type { RouteAdviceDetail } from "@/api/generated/client";
import { ReceiptText } from "@/components/receipt/ReceiptText";
import { Badge } from "@/components/ui/badge";
import {
  formatDays,
  formatKn,
  formatNm,
  formatSdr,
  formatTonnes,
  passagesOf,
  readComparison,
  ROUTE_NAME,
  savingLine,
  STATUS_NOTE,
  type RouteOption,
} from "@/lib/route-advice";
import { cn } from "@/lib/utils";
import { RouteStrip } from "./RouteStrip";

function OptionCard({ option, recommended }: { option: RouteOption; recommended: boolean }) {
  const rows: [string, string][] = [
    ["Distance", formatNm(option.distance_nm)],
    ["Days at sea", `${formatDays(option.sea_days)} at ${formatKn(option.speed_kn)}`],
    ["Fuel", `${formatTonnes(option.fuel_t)} · ${formatSdr(option.fuel_sdr)}`],
    ["Suez dues", option.route === "suez" ? formatSdr(option.suez_dues_sdr) : "none"],
  ];
  const passages = passagesOf(option);
  return (
    <section
      aria-label={ROUTE_NAME[option.route] ?? option.route}
      className={cn(
        "flex flex-col gap-3 rounded-xl border bg-card p-5",
        recommended ? "border-primary ring-1 ring-primary" : "",
      )}
    >
      <div className="flex items-center gap-2">
        <h3 className="text-base font-semibold">{ROUTE_NAME[option.route] ?? option.route}</h3>
        {recommended ? (
          <Badge className="ms-auto gap-1 bg-approved-wash text-approved-ink">
            <ShieldCheck className="size-3.5" aria-hidden /> Recommended
          </Badge>
        ) : null}
      </div>
      <p className="num text-2xl font-semibold" data-field="total_sdr" data-value={option.total_sdr}>
        {formatSdr(option.total_sdr)}
      </p>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-sm">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-muted-foreground">{k}</dt>
            <dd className="num text-end">{v}</dd>
          </div>
        ))}
      </dl>
      {passages.length ? (
        <p className="text-xs text-muted-foreground">Through {passages.join(", ")}</p>
      ) : null}
    </section>
  );
}

export function RouteDecision({
  advice,
  origin,
  destination,
}: {
  advice: RouteAdviceDetail;
  origin: string;
  destination: string;
}) {
  const { options, difference } = readComparison(advice.comparison);
  const rec = advice.recommendation ?? null;
  const numbers = advice.numbers ?? { headline: [], reasons: [], risks: [] };
  const note = advice.status ? STATUS_NOTE[advice.status] : "";
  const failed = advice.status === "output_invalid" || advice.status === "validation_failed";
  const ordered = [...options].sort((a, b) => Number(b.route === rec) - Number(a.route === rec));

  return (
    <div className="flex flex-col gap-5">
      <RouteStrip
        origin={origin}
        destination={destination}
        recommended={rec}
        routes={options.map((o) => o.route)}
      />

      {advice.headline ? (
        <p dir="auto" className="text-lg leading-relaxed font-medium">
          <ReceiptText text={advice.headline} numbers={numbers.headline ?? []} />
        </p>
      ) : null}
      {note ? (
        <p
          role={failed || advice.status === "not_permitted" ? "alert" : "status"}
          className={cn(
            "rounded-lg px-4 py-3 text-sm",
            failed ? "bg-alert-wash text-alert-ink" : "bg-muted text-muted-foreground",
          )}
        >
          {note}
        </p>
      ) : null}

      {ordered.length ? (
        <div className={cn("grid gap-4", ordered.length > 1 ? "md:grid-cols-2" : "")}>
          {ordered.map((o) => (
            <OptionCard key={o.route} option={o} recommended={o.route === rec} />
          ))}
        </div>
      ) : null}

      {rec && difference ? (
        <p className="rounded-lg bg-accent px-4 py-3 text-sm font-medium" data-testid="saving-line">
          {ROUTE_NAME[rec]} {savingLine(rec, difference)}
          <span className="ms-2 text-xs font-normal text-muted-foreground">
            (difference row: Cape − Suez, {formatNm(difference.change_distance_nm)})
          </span>
        </p>
      ) : null}

      {advice.reasons?.length ? (
        <section aria-labelledby="reasons-h">
          <h3 id="reasons-h" className="mb-2 text-sm font-semibold">
            Why
          </h3>
          <ul className="flex flex-col gap-2">
            {advice.reasons.map((r, i) => (
              <li key={i} dir="auto" className="rounded-lg border bg-card px-4 py-3 text-sm leading-relaxed">
                <ReceiptText text={r} numbers={numbers.reasons?.[i] ?? []} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {advice.risks?.length ? (
        <section aria-labelledby="risks-h">
          <h3 id="risks-h" className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
            <AlertTriangle className="size-4 text-waiting-ink" aria-hidden /> Risks to watch
          </h3>
          <ul className="flex flex-col gap-2">
            {advice.risks.map((r, i) => (
              <li
                key={i}
                dir="auto"
                className="rounded-lg border border-waiting/40 bg-waiting-wash/50 px-4 py-3 text-sm leading-relaxed"
              >
                <ReceiptText text={r} numbers={numbers.risks?.[i] ?? []} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <details className="group border-t pt-3">
        <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium">
          <ChevronDown className="size-4 transition-transform group-open:rotate-180" aria-hidden /> How we
          know
          <span className="ms-auto flex items-center gap-3 text-xs font-normal text-muted-foreground">
            <span className="flex items-center gap-1">
              <Cpu className="size-3.5" aria-hidden /> {advice.model_calls ?? 0} model calls
            </span>
            <span className="flex items-center gap-1">
              <Receipt className="size-3.5" aria-hidden />
              {(numbers.headline?.length ?? 0) +
                (numbers.reasons ?? []).reduce((n, r) => n + r.length, 0) +
                (numbers.risks ?? []).reduce((n, r) => n + r.length, 0)}{" "}
              numbers with receipts
            </span>
          </span>
        </summary>
        <div className="mt-3 grid gap-4 text-sm md:grid-cols-2">
          {advice.assumptions?.length ? (
            <div>
              <h4 className="mb-1 text-xs font-semibold text-muted-foreground">Assumptions</h4>
              <ul className="flex list-disc flex-col gap-1 ps-5">
                {advice.assumptions.map((a, i) => (
                  <li key={i} dir="auto">
                    {a}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {advice.sources?.length ? (
            <div>
              <h4 className="mb-1 text-xs font-semibold text-muted-foreground">Sources</h4>
              <ul className="flex flex-col gap-1">
                {advice.sources.map((s, i) => (
                  <li key={i} className="rounded-md border px-2.5 py-1.5 font-mono text-xs break-words">
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {advice.problems?.length ? (
            <div className="md:col-span-2">
              <h4 className="mb-1 text-xs font-semibold text-muted-foreground">
                Problems found by the checks
              </h4>
              <ul className="flex list-disc flex-col gap-1 ps-5">
                {advice.problems.map((p, i) => (
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
