// Arrival advice in the browser (Arrival advice web plan, ADR-070): the words for the API's options and statuses, and
// the formatting of their values. Nothing here computes a value: every option, time, wait and fuel figure comes from
// the arrival graph's code (`tools/arrival.py`); the UI only picks labels and signs.
import type { ArrivalOption } from "@/api/generated/client";

export const OPTION_LABEL: Record<ArrivalOption["option"], string> = {
  keep: "Keep speed",
  jit: "Slow down, arrive just in time",
  floor: "Slowest allowed speed",
  catch_up: "Speed up",
  cape: "Via the Cape",
};

/** Why there is no written recommendation, in plain words (the API's stop statuses). */
export const STATUS_NOTE: Record<string, string> = {
  on_time: "On time at its current speed: nothing to change.",
  late: "Late at its current speed, and no faster allowed speed makes the requested time.",
  not_at_sea: "This vessel is not at sea at the clock, so there is no arrival to plan.",
  not_destination: "That port is not this voyage's destination.",
  no_rta: "No requested time of arrival is known for this port call. Give one to plan against.",
  not_permitted: "Arrival advice is not part of your access.",
  no_data: "The data for this vessel is not available at the clock.",
  output_invalid: "The written advice could not be produced; the computed options below still stand.",
  validation_failed: "The written advice failed its number check; the computed options below still stand.",
  error: "The watch could not run this advice; the alert's own figures still stand.",
};

const fmt = (digits: number, sign: "auto" | "exceptZero" = "auto") =>
  new Intl.NumberFormat("en", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    signDisplay: sign,
  });

const speed = new Intl.NumberFormat("en", { minimumFractionDigits: 1, maximumFractionDigits: 2 });
export const formatKn = (v: number) => `${speed.format(v)} kn`;
export const formatHours = (v: number) => `${fmt(1).format(v)} h`;
export const formatTonnesChange = (v: number) => `${fmt(1, "exceptZero").format(v)} t`;
export const formatSdrChange = (v: number) => `${fmt(0, "exceptZero").format(v)} SDR`;
export const formatTonnes = (v: number) => `${fmt(1).format(v)} t`;
/** "2026-09-19T01:00Z" / "2026-09-19T01:00:00Z" → "2026-09-19 01:00Z" (seconds dropped, minutes kept). */
export const stamp = (iso: string | null | undefined) =>
  iso
    ? iso.replace(/T(\d{2}:\d{2})(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/, " $1$4").replace("+00:00", "Z")
    : "—";

/** The summary's fields the page shows (the OpenAPI type is an open object): read, never guessed. */
export function summaryOf(summary: Record<string, unknown> | null | undefined) {
  const s = summary ?? {};
  const str = (k: string) => (typeof s[k] === "string" ? (s[k] as string) : null);
  const num = (k: string) => (typeof s[k] === "number" ? (s[k] as number) : null);
  return {
    vesselId: num("vessel_id"),
    destination: str("destination"),
    rtaUtc: str("rta_utc"),
    rtaSource: str("rta_source"),
    location: str("location"),
    targetUtc: str("target_utc"),
    situation: str("situation"),
    ruleOption: str("rule_option"),
    currentSpeedKn: num("current_speed_kn"),
  };
}

/** `arrival_advice:<employee>:<date>:<vessel>:<n>` → the vessel and the number (for the list's labels). */
export function arrivalThreadParts(thread: string): { vessel: string; n: string; date: string } | null {
  const m = /^arrival_advice:\d+:(\d{4}-\d{2}-\d{2}):(\d+):(\d+)$/.exec(thread);
  return m ? { date: m[1]!, vessel: m[2]!, n: m[3]! } : null;
}
