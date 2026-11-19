// The signed-in top bar (plan §6.2): the products the asker has (from /me), the API status, the account menu.
import Link from "next/link";
import type { Me } from "@/lib/api-types";
import { cn } from "@/lib/utils";
import { HealthBadge } from "./HealthBadge";
import { NAV } from "./nav";
import { Logo } from "./Brand";
import { UserMenu } from "./UserMenu";
import { RunRecovery } from "@/components/providers/RunRecovery";

export function AppTopBar({ me, active, dark = false }: { me: Me; active: string; dark?: boolean }) {
  const items = NAV.filter((item) => item.show(me));
  const linkClass = (current: boolean) =>
    cn(
      "rounded-md px-3 py-2 text-sm font-medium transition-colors",
      dark
        ? current
          ? "bg-white/12 text-on-navy"
          : "text-on-navy-muted hover:bg-white/10 hover:text-on-navy"
        : current
          ? "bg-accent text-foreground"
          : "text-muted-foreground hover:bg-accent hover:text-foreground",
    );
  return (
    <>
      <header className={cn("relative z-10", dark ? "text-on-navy" : "border-b bg-card")}>
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2.5 rounded-md">
            <Logo dark={dark} />
            <span className="text-[1.05rem] font-semibold tracking-tight">PortPilot</span>
          </Link>
          <nav aria-label="Main" className="hidden items-center gap-1 lg:flex">
            {items.map((item) =>
              item.phase === null ? (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active === item.href ? "page" : undefined}
                  className={linkClass(active === item.href)}
                >
                  {item.label}
                </Link>
              ) : (
                <span
                  key={item.href}
                  aria-disabled="true"
                  title={`Arrives in phase ${item.phase}`}
                  className={cn(linkClass(false), "cursor-default opacity-60 hover:bg-transparent")}
                >
                  {item.label}
                </span>
              ),
            )}
          </nav>
          <div className="ms-auto flex items-center gap-3">
            <HealthBadge dark={dark} />
            <UserMenu me={me} dark={dark} />
          </div>
        </div>
      </header>
      <RunRecovery employeeId={me.employee_id} />
    </>
  );
}
