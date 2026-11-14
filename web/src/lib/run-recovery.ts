"use client";
// Per-tab, per-account identifiers only. Answers, questions and credentials never enter browser storage.
import { z } from "zod";

const KEY = "portpilot:pending-runs:v1";
const Entry = z.object({
  id: z
    .string()
    .min(1)
    .max(160)
    .regex(/^[\w:-]+$/),
  path: z
    .string()
    .max(500)
    .regex(/^\/(?:ask|routes|packs|views)(?:\/[^?#\\\s]*)?$/),
});
export type PendingRun = z.infer<typeof Entry>;
const Stored = z.object({ owner: z.number().int(), runs: z.array(Entry).max(100) });
let owner: number | null = null;
let pending: PendingRun[] = [];
const active = new Set<string>();
const listeners = new Set<() => void>();

function changed() {
  try {
    if (owner !== null) sessionStorage.setItem(KEY, JSON.stringify({ owner, runs: pending }));
    else sessionStorage.removeItem(KEY);
  } catch {
    /* Storage can be disabled; observation still works in this page. */
  }
  for (const listener of listeners) listener();
}

export function setRecoveryOwner(id: number | null) {
  if (owner === id) return;
  pending = [];
  active.clear();
  if (id !== null) {
    try {
      const saved = Stored.safeParse(JSON.parse(sessionStorage.getItem(KEY) ?? "null"));
      if (saved.success && saved.data.owner === id) pending = saved.data.runs;
    } catch {
      /* Malformed/unavailable storage is not trusted. */
    }
  }
  owner = id;
  changed();
}

export function subscribeRecovery(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
export const pendingRuns = () => pending.filter((run) => !active.has(run.id));
export function forgetRun(id: string) {
  pending = pending.filter((run) => run.id !== id);
  changed();
}

/** Capture the owner so a late completion after logout cannot touch the next account's runs. */
export function observeRun(id: string) {
  if (typeof window === "undefined") return () => undefined;
  const observedOwner = owner;
  const entry = Entry.safeParse({ id, path: window.location.pathname });
  if (owner !== null && entry.success && !pending.some((run) => run.id === id)) {
    pending = [...pending.slice(-99), entry.data];
  }
  active.add(id);
  changed();
  return (finished: boolean) => {
    if (owner !== observedOwner) return;
    active.delete(id);
    if (finished) pending = pending.filter((run) => run.id !== id);
    changed();
  };
}
