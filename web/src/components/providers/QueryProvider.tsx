"use client";
// Server state (plan §3): retries only for 429 / 503 (the API says when to come back), never for other 4xx.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { BffError } from "@/lib/bff/client";

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            retry: (count, error) =>
              count < 2 && error instanceof BffError && (error.status === 429 || error.status === 503),
            retryDelay: (_count, error) =>
              error instanceof BffError && error.retryAfter ? error.retryAfter * 1000 : 2000,
          },
        },
      }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
