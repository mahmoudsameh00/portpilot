// The top bar: wordmark, the product navigation, the ask shortcut and the user. "dark" sits on the night-ops band.
import { Command, Search } from "lucide-react";
import Link from "next/link";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { home } from "@/concept/fixtures";
import { Logo } from "./Brand";

const NAV = [
  { href: "/concept", label: "Today" },
  { href: "/concept/answer", label: "Ask" },
  { href: "/concept/pack", label: "Weekly pack" },
  { href: "#", label: "Voyages" },
  { href: "#", label: "Routes" },
  { href: "#", label: "Charts" },
];

export function TopBar({ active, dark = false }: { active: string; dark?: boolean }) {
  return (
    <header className={cn("relative z-10", dark ? "text-on-navy" : "border-b bg-card")}>
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 sm:px-6">
        <Link href="/concept" className="flex items-center gap-2.5 rounded-md">
          <Logo dark={dark} />
          <span className="text-[1.05rem] font-semibold tracking-tight">PortPilot</span>
        </Link>
        <nav aria-label="Main" className="hidden items-center gap-1 lg:flex">
          {NAV.map((item) => (
            <Link
              key={item.label}
              href={item.href}
              aria-current={active === item.href ? "page" : undefined}
              className={cn(
                "rounded-md px-3 py-2 text-sm font-medium transition-colors",
                dark
                  ? "text-on-navy-muted hover:bg-white/10 hover:text-on-navy aria-[current=page]:bg-white/12 aria-[current=page]:text-on-navy"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground aria-[current=page]:bg-accent aria-[current=page]:text-foreground",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="ms-auto flex items-center gap-3">
          <Badge
            variant="outline"
            className={cn("hidden sm:inline-flex", dark && "border-white/20 text-on-navy-muted")}
          >
            Concept · sample data
          </Badge>
          <Link
            href="/concept/answer"
            className={cn(
              "flex h-9 items-center gap-2 rounded-md border px-3 text-sm transition-colors md:w-56",
              dark
                ? "border-white/15 bg-white/5 text-on-navy-muted hover:border-lane"
                : "bg-background text-muted-foreground hover:border-primary",
            )}
          >
            <Search className="size-4" aria-hidden />
            <span className="sr-only md:not-sr-only">Ask PortPilot…</span>
            <kbd className="ms-auto hidden items-center gap-0.5 font-mono text-xs md:flex">
              <Command className="size-3" aria-hidden />K
            </kbd>
          </Link>
          <Avatar className="size-9" title={`${home.user.name} — ${home.user.role}`}>
            <AvatarFallback
              className={cn(dark ? "bg-white text-navy" : "bg-navy text-white", "text-sm font-semibold")}
            >
              {home.user.initial}
            </AvatarFallback>
          </Avatar>
        </div>
      </div>
    </header>
  );
}
