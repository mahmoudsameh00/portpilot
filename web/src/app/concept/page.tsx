// Concept — "Today" (plan §6.0, D-FE-3; owner 2026-11-06: night-ops hero + control-tower KPIs + bento services).
import {
  AlertTriangle,
  ArrowRight,
  ChartColumnBig,
  FileCheck2,
  Radar as RadarIcon,
  Route,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { StatusBadge } from "@/components/concept/StatusBadge";
import { LaneMap } from "@/components/home/LaneMap";
import { NumberChip } from "@/components/receipt/NumberChip";
import { ReceiptText } from "@/components/receipt/ReceiptText";
import { TopBar } from "@/components/shell/TopBar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { BillingChart, ContainerStacks, Radar, RouteCompare, Sparkline } from "@/components/viz/charts";
import { home, WEEKS } from "@/concept/fixtures";
import { cn } from "@/lib/utils";

const LEVEL = {
  high: "bg-alert-wash text-alert-ink",
  medium: "bg-waiting-wash text-waiting-ink",
  low: "bg-accent text-primary",
} as const;

export default function ConceptHome() {
  const d = home;
  const high = d.alerts.filter((a) => a.level === "high").length;
  const saves = d.route.cape.cost - d.route.suez.cost;
  const fasterDays = d.route.cape.days - d.route.suez.days;

  return (
    <>
      <div className="night-ops pb-28 text-on-navy">
        <TopBar dark active="/concept" />
        <section className="mx-auto grid max-w-7xl items-center gap-8 px-4 pt-6 sm:px-6 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.3fr)]">
          <div>
            <p className="flex items-center gap-2 text-sm text-on-navy-muted">
              <span className="relative flex size-2">
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-lane opacity-60 motion-reduce:hidden" />
                <span className="relative inline-flex size-2 rounded-full bg-lane" />
              </span>
              {d.today}, last sync {d.lastRun}
            </p>
            <h1 className="mt-4 text-4xl font-semibold sm:text-5xl">Good morning, {d.user.name}.</h1>
            <p className="mt-3 max-w-md text-lg text-on-navy-muted">
              One pack waits for your decision and {high} voyages need attention.
            </p>

            <form
              action="/concept/answer"
              className="mt-7 flex gap-2 rounded-xl border border-white/15 bg-white/[0.06] p-1.5 backdrop-blur"
            >
              <label htmlFor="ask" className="sr-only">
                Ask PortPilot
              </label>
              <Sparkles className="ms-2 size-5 shrink-0 self-center text-lane" aria-hidden />
              <input
                id="ask"
                name="q"
                placeholder="Ask about billing, voyages or routes, in English or Arabic"
                className="h-11 min-w-0 flex-1 bg-transparent px-2 text-sm text-on-navy outline-none placeholder:text-on-navy-muted/80"
              />
              <Button type="submit" size="lg" className="h-11 bg-white text-navy hover:bg-white/90">
                Ask
              </Button>
            </form>
            <ul className="mt-3 flex flex-wrap gap-2">
              {d.starters.map((q) => (
                <li key={q}>
                  <Link
                    href="/concept/answer"
                    dir="auto"
                    className="block rounded-full border border-white/15 px-3 py-1.5 text-xs text-on-navy-muted transition-colors hover:border-lane hover:text-on-navy"
                  >
                    {q}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <LaneMap className="aspect-[1000/671] w-full" />
            <div className="mt-1 flex flex-wrap justify-end gap-4 text-xs text-on-navy-muted">
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-5 border-t-2 border-lane" /> Via Suez
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-5 border-t-2 border-dotted border-lane" /> Via the Cape
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block size-2 rounded-full bg-white" /> Port Said (home)
              </span>
            </div>
          </div>
        </section>
      </div>

      <main className="mx-auto -mt-20 max-w-7xl px-4 pb-16 sm:px-6">
        {/* Control tower: the four numbers that matter this week, each with its receipt. */}
        <section aria-label="This week" className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {d.kpis.map((k) => (
            <Card key={k.label} className="gap-3 py-5 shadow-float">
              <CardHeader className="px-5">
                <CardDescription>{k.label}</CardDescription>
                <CardTitle className="text-2xl font-semibold tracking-tight">
                  <NumberChip span={{ ...k.value, row: 0, start: 0, end: k.value.text.length }} />
                </CardTitle>
              </CardHeader>
              <CardContent className="flex items-end gap-3 px-5">
                <p
                  className={cn(
                    "shrink-0 text-xs font-medium",
                    k.label.startsWith("Overdue") || k.trend === "down"
                      ? "text-alert-ink"
                      : "text-muted-foreground",
                  )}
                >
                  {k.delta}
                </p>
                <Sparkline values={k.series} tone={k.label.startsWith("Overdue") ? "alert" : "primary"} />
              </CardContent>
            </Card>
          ))}
        </section>

        {/* Bento: one tile per service, each with one action. */}
        <section aria-label="Your services" className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-6">
          <Card className="lg:col-span-3">
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileCheck2 className="size-4 text-primary" aria-hidden /> Weekly finance pack
                </CardTitle>
                <StatusBadge kind="draft" />
              </div>
              <CardDescription>
                <span className="font-mono">{d.pack.week}</span> is drafted, checked and waiting for your
                decision.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
              <p className="text-sm leading-relaxed">
                <ReceiptText text={d.pack.line.text} numbers={d.pack.line.numbers} />
              </p>
              <ol className="grid grid-cols-5 gap-2 sm:grid-cols-10" aria-label="Slides">
                {Array.from({ length: d.pack.slides }, (_, i) => (
                  <li
                    key={i}
                    className="relative aspect-[16/10] rounded-md border bg-background p-1"
                    title={`Slide ${i + 1}`}
                  >
                    <span className="block h-1 w-3/4 rounded-full bg-navy/70" />
                    <span className="mt-1 flex h-[55%] items-end gap-[2px]">
                      {[0.5, 0.8, 0.6, 1].map((h, k) => (
                        <span
                          key={k}
                          className="flex-1 rounded-t-[1px] bg-chart-1/50"
                          style={{ height: `${h * (0.5 + ((i * 7 + k * 3) % 5) / 10) * 100}%` }}
                        />
                      ))}
                    </span>
                    {i === 2 || i === 6 ? (
                      <span className="absolute -top-1 -end-1 size-2.5 rounded-full bg-waiting ring-2 ring-card" />
                    ) : null}
                  </li>
                ))}
              </ol>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="flex items-center gap-1.5 text-sm text-waiting-ink">
                  <AlertTriangle className="size-4" aria-hidden /> {d.pack.notes} Validator notes to look at
                </p>
                <Button asChild>
                  <Link href="/concept/pack">
                    Review the pack <ArrowRight aria-hidden />
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="lg:col-span-3">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <RadarIcon className="size-4 text-primary" aria-hidden /> Voyage watch
              </CardTitle>
              <CardDescription>Checked every 12 hours. Next check 22:30.</CardDescription>
            </CardHeader>
            <CardContent className="grid items-center gap-4 sm:grid-cols-[11rem_minmax(0,1fr)]">
              <div className="mx-auto size-44">
                <Radar blips={d.alerts} />
              </div>
              <ul className="flex flex-col gap-2">
                {d.alerts.slice(0, 4).map((a) => (
                  <li key={a.vessel} className="flex items-start gap-2 text-sm">
                    <span
                      className={cn(
                        "mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[0.7rem] font-semibold capitalize",
                        LEVEL[a.level],
                      )}
                    >
                      {a.level}
                    </span>
                    <span>
                      <span className="font-medium">{a.vessel}</span>
                      <span className="text-muted-foreground"> — {a.text}</span>
                    </span>
                  </li>
                ))}
                <li>
                  <Button variant="outline" size="sm" className="mt-1">
                    Open the watch
                  </Button>
                </li>
              </ul>
            </CardContent>
          </Card>

          <Card className="lg:col-span-4">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <ChartColumnBig className="size-4 text-primary" aria-hidden /> Billing against budget
              </CardTitle>
              <CardDescription>Last 12 weeks, million SDR. The report week is underlined.</CardDescription>
            </CardHeader>
            <CardContent>
              <BillingChart weeks={WEEKS} billed={d.billing.billed} budget={d.billing.budget} compact />
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Route className="size-4 text-primary" aria-hidden /> Route advice
              </CardTitle>
              <CardDescription className="flex items-center gap-2 font-mono text-foreground">
                {d.route.origin} <ArrowRight className="size-3.5 text-muted-foreground" aria-hidden />{" "}
                {d.route.destination}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <RouteCompare suez={d.route.suez} cape={d.route.cape} />
              <p className="rounded-md bg-accent px-3 py-2 text-sm">
                <span className="font-semibold text-primary">Suez</span> saves{" "}
                <span className="num font-semibold">{saves.toFixed(2)}M SDR</span> and{" "}
                <span className="num font-semibold">{fasterDays.toFixed(1)} days</span>.
              </p>
            </CardContent>
          </Card>

          <Card className="lg:col-span-3">
            <CardHeader>
              <CardTitle className="text-base">Overdue receivables by age</CardTitle>
              <CardDescription>One container = 0.5M SDR. Older stacks need a call.</CardDescription>
            </CardHeader>
            <CardContent>
              <ContainerStacks buckets={d.ageing} />
            </CardContent>
          </Card>

          <Card className="lg:col-span-3">
            <CardHeader>
              <CardTitle className="text-base">Ask for a chart</CardTitle>
              <CardDescription>
                Charts come from the finance views, in the weekly pack&apos;s colours.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {[
                "Collections, last 26 weeks",
                "Billing by customer, W45",
                "Overdue trend by bucket",
                "Suez transits per day",
              ].map((c) => (
                <Badge key={c} variant="secondary" className="h-8 px-3 text-sm font-normal">
                  {c}
                </Badge>
              ))}
            </CardContent>
          </Card>
        </section>
      </main>
    </>
  );
}
