// Home (plan §6.0 (1), MASTER v2; "Today" until D-FE-11 removed its tab — the wordmark opens it): the night-ops
// band with the lanes, then the asker's services from /me.
// F2 builds the shell; each tile names the phase that brings its page (live lines come with F3–F6 and F0b).
import { ChartColumnBig, FileCheck2, MessageSquareText, Radar, Route, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { LaneMap } from "@/components/home/LaneMap";
import { AppTopBar } from "@/components/shell/AppTopBar";
import { NAV } from "@/components/shell/nav";
import { Badge } from "@/components/ui/badge";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getSession } from "@/lib/session";

const TILES: Record<string, { icon: React.ComponentType<{ className?: string }>; text: string }> = {
  "/ask": {
    icon: MessageSquareText,
    text: "Ask about billing, receivables, voyages or routes — in English or Arabic. Every number comes with its receipt.",
  },
  "/packs": {
    icon: FileCheck2,
    text: "Reports: review the weekly finance pack slide by slide, edit, then approve the whole pack or ask for a rewrite.",
  },
  "/views": {
    icon: ChartColumnBig,
    text: "Ask for a chart of the finance data in words, or choose one from the catalogue.",
  },
  "/finance": {
    icon: ChartColumnBig,
    text: "Dashboards: the finance pages — overview, revenue, receivables, customers, exceptions — from the same views as Power BI.",
  },
  "/voyages": { icon: Radar, text: "Voyage alerts by severity, the latest watch run and its brief." },
  "/routes": { icon: Route, text: "Compare Suez and the Cape on cost and time for a port pair." },
};

function greeting(): string {
  const hour = Number(
    new Intl.DateTimeFormat("en-GB", { hour: "numeric", hour12: false, timeZone: "Africa/Cairo" }).format(
      new Date(),
    ),
  );
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

export default async function HomePage() {
  const session = await getSession();
  if (session.kind !== "signed-in") return null; // the layout already sent the user to sign in
  const { me } = session;
  const services = NAV.filter((item) => item.show(me));

  return (
    <>
      <div className="night-ops pb-16 text-on-navy">
        <AppTopBar me={me} active="/" dark />
        <section className="mx-auto grid max-w-7xl items-center gap-8 px-4 pt-6 sm:px-6 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.3fr)]">
          <div>
            <p className="flex items-center gap-2 text-sm text-on-navy-muted">
              <ShieldCheck className="size-4 text-lane" aria-hidden />
              Employee {me.employee_id}, {me.role} in {me.department}
            </p>
            <h1 className="mt-4 text-4xl font-semibold sm:text-5xl">{greeting()}.</h1>
            <p className="mt-3 max-w-md text-lg text-on-navy-muted">
              {services.length === 1
                ? "One service is open to you."
                : `${services.length} services are open to you.`}{" "}
              What you see follows your access; the API checks every request again.
            </p>
          </div>
          <LaneMap className="aspect-[1000/671] w-full" />
        </section>
      </div>

      <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
        <h2 className="text-lg font-semibold">Your services</h2>
        <ul className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {services.map((item) => {
            const tile = TILES[item.href];
            const Icon = tile?.icon ?? MessageSquareText;
            return (
              <li key={item.href}>
                <Card
                  className={
                    item.phase === null ? "relative h-full transition-colors hover:border-primary" : "h-full"
                  }
                >
                  <CardHeader>
                    <div className="flex items-center justify-between gap-3">
                      <CardTitle className="flex items-center gap-2 text-base">
                        <Icon className="size-4 text-primary" /> {item.label}
                      </CardTitle>
                      {item.phase ? (
                        <Badge variant="secondary" className="font-normal">
                          Arrives in {item.phase}
                        </Badge>
                      ) : null}
                    </div>
                    <CardDescription>{tile?.text}</CardDescription>
                    {item.phase === null ? (
                      <Link
                        href={item.href}
                        className="absolute inset-0 rounded-xl"
                        aria-label={`Open ${item.label}`}
                      />
                    ) : null}
                  </CardHeader>
                </Card>
              </li>
            );
          })}
        </ul>
      </main>
    </>
  );
}
