"use client";
// API status from /health/ready (plan §6.2): counts and states only, refreshed every minute.
import { useQuery } from "@tanstack/react-query";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Ready } from "@/lib/api-types";
import { cn } from "@/lib/utils";

async function readyState(): Promise<Ready | null> {
  const res = await fetch("/bff/health/ready", {
    headers: { accept: "application/json" },
    cache: "no-store",
  });
  if (res.status === 200 || res.status === 503) return (await res.json()) as Ready;
  return null; // 502 from the BFF: the API is not reachable
}

export function HealthBadge({ dark = false }: { dark?: boolean }) {
  const { data, isPending } = useQuery({
    queryKey: ["health"],
    queryFn: readyState,
    refetchInterval: 60_000,
  });
  const state = isPending ? "checking" : data === null || data === undefined ? "offline" : data.status;
  const label = {
    checking: "Checking API",
    ready: "API ready",
    degraded: "API degraded",
    offline: "API offline",
  }[state];
  const dot = {
    checking: "bg-muted-foreground",
    ready: "bg-approved",
    degraded: "bg-waiting",
    offline: "bg-destructive",
  }[state];
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          role="status"
          className={cn(
            "hidden items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs sm:inline-flex",
            dark ? "border-white/15 text-on-navy-muted" : "text-muted-foreground",
          )}
        >
          <span className={cn("size-2 rounded-full", dot)} aria-hidden />
          {label}
        </span>
      </TooltipTrigger>
      <TooltipContent>
        {data
          ? data.components.map((c) => `${c.name} ${c.ok ? "ok" : "down"}`).join(" · ")
          : "No answer from the API"}
      </TooltipContent>
    </Tooltip>
  );
}
