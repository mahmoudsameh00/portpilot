"use client";
// One arrival advice (Arrival advice web plan): GET /arrival-advice/{thread} — the asker's own (the CEO's: any); the
// API decides. The advice in full, then the request card to ask again.
import { useQuery } from "@tanstack/react-query";
import { Anchor, Loader2 } from "lucide-react";
import Link from "next/link";
import { getArrivalAdviceApiV1ArrivalAdviceThreadIdGet as getAdvice } from "@/api/generated/client";
import { BffError } from "@/lib/bff/client";
import { arrivalThreadParts } from "@/lib/arrival-advice";
import { AdviceCard, ArrivalRequest } from "./Arrival";

export function ArrivalDetail({ thread }: { thread: string }) {
  const { data, isPending, error } = useQuery({
    queryKey: ["arrival-advice", thread],
    queryFn: () => getAdvice(thread),
    retry: false,
  });
  const p = arrivalThreadParts(thread);
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end gap-3">
        <div className="me-auto">
          <h1 className="flex items-center gap-2 text-2xl font-semibold">
            <Anchor className="size-6 text-primary" aria-hidden /> Arrival advice
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {p ? `Vessel ${p.vessel}, asked at the clock of ${p.date} (#${p.n}).` : thread}
          </p>
        </div>
        <Link href="/voyages" className="text-sm font-medium text-primary hover:underline">
          Back to the voyage watch
        </Link>
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="min-w-0">
          {isPending ? <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden /> : null}
          {error ? (
            <p role="alert" className="text-sm text-alert-ink">
              {error instanceof BffError && error.status === 404
                ? "This advice is not on the chart."
                : "The advice could not be loaded."}
            </p>
          ) : null}
          {data ? <AdviceCard advice={data} /> : null}
        </div>
        <ArrivalRequest />
      </div>
    </div>
  );
}
