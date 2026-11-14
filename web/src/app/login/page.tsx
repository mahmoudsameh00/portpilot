// Sign in (plan §6.1): the night-ops side tells what PortPilot is; the form side does one thing.
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { LaneMap } from "@/components/home/LaneMap";
import { Logo } from "@/components/shell/Brand";
import { getSession, safeNext } from "@/lib/session";
import { LoginForm } from "./LoginForm";

export const metadata: Metadata = { title: "Sign in — PortPilot" };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const next = safeNext((await searchParams).next);
  const session = await getSession();
  if (session.kind === "signed-in") redirect(next);

  return (
    <main className="grid min-h-dvh lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      <section className="night-ops relative hidden flex-col justify-between overflow-hidden p-10 text-on-navy lg:flex">
        <div className="flex items-center gap-2.5">
          <Logo dark />
          <span className="text-lg font-semibold tracking-tight">PortPilot</span>
        </div>
        <LaneMap className="my-6 w-full" />
        <div className="max-w-md">
          <p className="text-2xl font-semibold tracking-tight">Port and logistics intelligence.</p>
          <p className="mt-2 text-on-navy-muted">
            Finance packs, voyages and routes in one place — and every number comes with its receipt.
          </p>
        </div>
      </section>

      <section className="flex flex-col justify-center px-6 py-12 sm:px-12">
        <div className="mx-auto w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <Logo dark={false} />
            <span className="text-lg font-semibold tracking-tight">PortPilot</span>
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">Sign in</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Use the work email your PortPilot admin set up for you.
          </p>
          <LoginForm next={next} apiDown={session.kind === "api-down"} />
          <p className="mt-8 text-xs text-muted-foreground">
            No account yet, or locked out? Ask the PortPilot admin — logins are created and reset there.
          </p>
        </div>
      </section>
    </main>
  );
}
