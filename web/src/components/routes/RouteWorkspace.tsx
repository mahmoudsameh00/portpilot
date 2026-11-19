"use client";
// Route advice (plan §6.6): origin → destination (UN/LOCODE) and the vessel → POST /route-advice (a run, SSE) → the
// decision view; earlier advice listed beside it (GET /route-advice) and opened at /routes/<thread>.
// The form checks only the API's own field rules (RouteIn) before sending; the API decides everything else.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, Loader2, Route as RouteIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  getRouteAdviceApiV1RouteAdviceThreadIdGet as getAdvice,
  listRouteAdviceApiV1RouteAdviceGet as listAdvice,
  routeAdviceApiV1RouteAdvicePost as postAdvice,
  type RouteIn,
  type RunEventSchema,
} from "@/api/generated/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { BffError } from "@/lib/bff/client";
import { LOCODE, ROUTE_STEPS, threadParts, VESSEL_TYPES } from "@/lib/route-advice";
import { RunObservationError, streamRun } from "@/lib/runs";
import { cn } from "@/lib/utils";
import { RouteDecision } from "./RouteDecision";

type Mode = "fleet" | "type";

/** The API's RouteIn rules, said in words before sending (the API checks them again). */
function formProblem(body: RouteIn): string | null {
  if (!LOCODE.test(body.origin)) return "Origin must be a 5-letter UN/LOCODE, for example EGPSD.";
  if (!LOCODE.test(body.destination)) return "Destination must be a 5-letter UN/LOCODE, for example NLRTM.";
  if (body.origin === body.destination) return "Origin and destination must differ.";
  if (body.vessel_id == null && (!body.vessel_type || !body.condition || !body.scnt_tons))
    return "Give a vessel id, or the vessel type, condition and SCNT tons.";
  if (body.speed_kn != null && (body.speed_kn < 4 || body.speed_kn > 25)) return "Speed must be 4–25 knots.";
  return null;
}

function Steps({ seen, done }: { seen: Set<string>; done: boolean }) {
  return (
    <ol className="flex flex-wrap items-center gap-1.5" aria-label="What is being done" aria-live="polite">
      {ROUTE_STEPS.filter((s) => seen.has(s.node) || s.node === "inputs").map((s, k, all) => {
        const finished = done || k < all.length - 1;
        return (
          <li key={s.node} className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span
              className={cn(
                "grid size-4 place-items-center rounded-full",
                finished ? "bg-primary text-primary-foreground" : "bg-accent text-primary",
              )}
            >
              {finished ? (
                <Check className="size-3" aria-hidden />
              ) : (
                <Loader2 className="size-3 animate-spin" aria-hidden />
              )}
            </span>
            {s.label}
            {k < all.length - 1 ? <span className="mx-1 h-px w-4 bg-border" aria-hidden /> : null}
          </li>
        );
      })}
    </ol>
  );
}

function History({ current }: { current?: string }) {
  const { data, isPending, error } = useQuery({ queryKey: ["route-advice"], queryFn: () => listAdvice() });
  const rows = [...(data ?? [])].sort((a, b) => b.last_at.localeCompare(a.last_at));
  return (
    <Card className="gap-3">
      <CardHeader>
        <CardTitle className="text-base">Earlier advice</CardTitle>
      </CardHeader>
      <CardContent>
        {isPending ? <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden /> : null}
        {error ? (
          <p role="alert" className="text-sm text-alert-ink">
            The list could not be loaded.
          </p>
        ) : null}
        <ul className="flex flex-col gap-1.5" aria-label="Earlier advice">
          {rows.map((r) => {
            const p = threadParts(r.thread_id);
            return (
              <li key={r.thread_id}>
                <Link
                  href={`/routes/${encodeURIComponent(r.thread_id)}`}
                  aria-current={r.thread_id === current ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors hover:border-primary",
                    r.thread_id === current ? "border-primary bg-accent" : "",
                  )}
                >
                  <span className="font-mono font-semibold">
                    {p ? `${p.origin} → ${p.destination}` : r.thread_id}
                  </span>
                  <span className="text-xs text-muted-foreground">{p ? `${p.date} · #${p.n}` : null}</span>
                  <span className="ms-auto text-xs text-muted-foreground">
                    {(r.status ?? r.state).replaceAll("_", " ")}
                  </span>
                </Link>
              </li>
            );
          })}
          {!isPending && !error && rows.length === 0 ? (
            <li className="text-sm text-muted-foreground">No advice yet. Ask for the first one.</li>
          ) : null}
        </ul>
      </CardContent>
    </Card>
  );
}

function Detail({ thread }: { thread: string }) {
  const { data, isPending, error } = useQuery({
    queryKey: ["route-advice", thread],
    queryFn: () => getAdvice(thread),
    retry: false,
  });
  const p = threadParts(thread);
  if (isPending) return <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden />;
  if (error || !data)
    return (
      <p role="alert" className="text-sm text-alert-ink">
        {error instanceof BffError && error.status === 404
          ? "This advice is not on the chart."
          : "The advice could not be loaded."}
      </p>
    );
  return <RouteDecision advice={data} origin={p?.origin ?? "—"} destination={p?.destination ?? "—"} />;
}

/** `prefill` (from the URL, e.g. "Compare routes" on an arrival advice): a vessel and a destination to start from. */
export function RouteWorkspace({
  thread,
  prefill,
}: {
  thread?: string;
  prefill?: { vessel?: string; destination?: string };
}) {
  const router = useRouter();
  const qc = useQueryClient();
  const parts = thread ? threadParts(thread) : null;
  const [origin, setOrigin] = useState(parts?.origin ?? "");
  const [destination, setDestination] = useState(parts?.destination ?? prefill?.destination ?? "");
  const [mode, setMode] = useState<Mode>("fleet");
  const [vesselId, setVesselId] = useState(prefill?.vessel ?? "");
  const [vesselType, setVesselType] = useState<string>(VESSEL_TYPES[1]);
  const [condition, setCondition] = useState<"Laden" | "Ballast">("Laden");
  const [scnt, setScnt] = useState("");
  const [speed, setSpeed] = useState("");
  const [busy, setBusy] = useState(false);
  const [seen, setSeen] = useState<Set<string>>(new Set());
  const [message, setMessage] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const body: RouteIn = {
      origin: origin.trim().toUpperCase(),
      destination: destination.trim().toUpperCase(),
      ...(mode === "fleet"
        ? { vessel_id: vesselId ? Number(vesselId) : null }
        : { vessel_type: vesselType, condition, scnt_tons: scnt ? Number(scnt) : null }),
      ...(speed ? { speed_kn: Number(speed) } : {}),
    };
    const problem = formProblem(body);
    if (problem) {
      setMessage(problem);
      return;
    }
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
      await qc.invalidateQueries({ queryKey: ["route-advice"] });
      if (accepted.thread_id) router.push(`/routes/${encodeURIComponent(accepted.thread_id)}`);
    } catch (error) {
      setMessage(
        error instanceof RunObservationError
          ? error.message
          : error instanceof BffError
            ? error.status === 403
              ? "Route advice is not part of your access."
              : error.title
            : "The advice could not be asked for. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  const field = "h-10";
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold">
          <RouteIcon className="size-6 text-primary" aria-hidden /> Route advice
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Suez or the Cape: distance, days, fuel and dues priced by code, then explained.
        </p>
      </div>

      <form onSubmit={submit} className="flex flex-col gap-4 rounded-xl border bg-card p-5" noValidate>
        <div className="grid gap-4 sm:grid-cols-[1fr_auto_1fr] sm:items-end">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="origin">Origin (UN/LOCODE)</Label>
            <Input
              id="origin"
              className={cn(field, "font-mono uppercase")}
              maxLength={5}
              placeholder="EGPSD"
              value={origin}
              onChange={(e) => setOrigin(e.target.value.toUpperCase())}
              autoComplete="off"
            />
          </div>
          <ArrowRight className="mx-auto mb-2.5 hidden size-5 text-muted-foreground sm:block" aria-hidden />
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="destination">Destination (UN/LOCODE)</Label>
            <Input
              id="destination"
              className={cn(field, "font-mono uppercase")}
              maxLength={5}
              placeholder="NLRTM"
              value={destination}
              onChange={(e) => setDestination(e.target.value.toUpperCase())}
              autoComplete="off"
            />
          </div>
        </div>

        <fieldset className="flex flex-col gap-3">
          <legend className="mb-2 text-sm font-medium">Vessel</legend>
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Vessel">
            {(
              [
                ["fleet", "One of our vessels"],
                ["type", "A vessel type"],
              ] as const
            ).map(([m, label]) => (
              <label
                key={m}
                className={cn(
                  "flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1.5 text-sm",
                  mode === m ? "border-primary bg-accent" : "",
                )}
              >
                <input
                  type="radio"
                  name="mode"
                  value={m}
                  checked={mode === m}
                  onChange={() => setMode(m)}
                  className="accent-primary"
                />
                {label}
              </label>
            ))}
          </div>
          {mode === "fleet" ? (
            <div className="flex max-w-xs flex-col gap-1.5">
              <Label htmlFor="vessel-id">Vessel id</Label>
              <Input
                id="vessel-id"
                className={cn(field, "font-mono")}
                inputMode="numeric"
                value={vesselId}
                onChange={(e) => setVesselId(e.target.value.replace(/\D/g, ""))}
              />
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr]">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="vessel-type">Vessel type</Label>
                <select
                  id="vessel-type"
                  className="h-10 rounded-md border bg-background px-3 text-sm"
                  value={vesselType}
                  onChange={(e) => setVesselType(e.target.value)}
                >
                  {VESSEL_TYPES.map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="condition">Condition</Label>
                <select
                  id="condition"
                  className="h-10 rounded-md border bg-background px-3 text-sm"
                  value={condition}
                  onChange={(e) => setCondition(e.target.value as "Laden" | "Ballast")}
                >
                  <option>Laden</option>
                  <option>Ballast</option>
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="scnt">SCNT tons</Label>
                <Input
                  id="scnt"
                  className={cn(field, "font-mono")}
                  inputMode="decimal"
                  value={scnt}
                  onChange={(e) => setScnt(e.target.value.replace(/[^\d.]/g, ""))}
                />
              </div>
            </div>
          )}
        </fieldset>

        <div className="flex flex-wrap items-end gap-4">
          <div className="flex w-40 flex-col gap-1.5">
            <Label htmlFor="speed">Speed, knots (optional)</Label>
            <Input
              id="speed"
              className={cn(field, "font-mono")}
              inputMode="decimal"
              placeholder="4–25"
              value={speed}
              onChange={(e) => setSpeed(e.target.value.replace(/[^\d.]/g, ""))}
            />
          </div>
          <Button type="submit" size="lg" className="ms-auto h-11" disabled={busy}>
            {busy ? <Loader2 className="animate-spin" aria-hidden /> : <RouteIcon aria-hidden />}
            Compare Suez and Cape
          </Button>
        </div>
        {busy ? <Steps seen={seen} done={false} /> : null}
        {message ? (
          <p role="alert" className="text-sm text-alert-ink">
            {message}
          </p>
        ) : null}
      </form>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="min-w-0">
          {thread ? (
            <Detail thread={thread} />
          ) : (
            <p className="rounded-xl border border-dashed px-5 py-8 text-sm text-muted-foreground">
              Try CNSHA → NLRTM for one of our vessels by its id, or for a laden containership of 80,000 SCNT
              tons. Distance, fuel and dues are priced by code; the advice explains them.
            </p>
          )}
        </div>
        <History current={thread} />
      </div>
    </div>
  );
}
