// Route advice in the browser (Frontend plan §6.6): the API's `comparison` rows read with a schema (the OpenAPI type
// is an open object), and the formatting of their values. Nothing here computes a value: the difference row
// (Cape − Suez) comes from the graph's own `route.difference`; the UI only picks words and signs for it.
import { z } from "zod";

const num = z.number();

export const RouteOptionZ = z.object({
  route: z.enum(["suez", "cape", "direct"]),
  passages: z.unknown().optional(),
  distance_nm: num,
  speed_kn: num,
  sea_days: num,
  fuel_t: num,
  fuel_sdr: num,
  suez_dues_sdr: num,
  total_sdr: num,
});
export type RouteOption = z.infer<typeof RouteOptionZ>;

export const RouteDifferenceZ = z.object({
  route: z.literal("difference"),
  change_distance_nm: num,
  change_sea_days: num,
  change_fuel_t: num,
  change_fuel_sdr: num,
  change_total_sdr: num,
  change_dues_sdr: num,
  cheaper_route: z.enum(["suez", "cape"]),
});
export type RouteDifference = z.infer<typeof RouteDifferenceZ>;

/** The route rows and the difference row of a `comparison`; a row outside the shape is left out (never guessed). */
export function readComparison(rows: readonly unknown[] | null | undefined): {
  options: RouteOption[];
  difference: RouteDifference | null;
} {
  const options: RouteOption[] = [];
  let difference: RouteDifference | null = null;
  for (const row of rows ?? []) {
    const opt = RouteOptionZ.safeParse(row);
    if (opt.success) options.push(opt.data);
    const diff = RouteDifferenceZ.safeParse(row);
    if (diff.success) difference = diff.data;
  }
  return { options, difference };
}

/** The passages a route goes through, when the API gives them as names. */
export function passagesOf(option: RouteOption): string[] {
  const p = option.passages;
  if (Array.isArray(p)) return p.filter((x): x is string => typeof x === "string");
  return typeof p === "string" && p ? [p] : [];
}

const fmt = (digits: number, sign: "auto" | "never" = "auto") =>
  new Intl.NumberFormat("en", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    signDisplay: sign,
  });

export const formatSdr = (v: number) => `${fmt(2).format(v)} SDR`;
export const formatDays = (v: number) => `${fmt(2).format(v)} days`;
export const formatNm = (v: number) => `${fmt(0).format(v)} nm`;
export const formatTonnes = (v: number) => `${fmt(1).format(v)} t`;
export const formatKn = (v: number) => `${fmt(1).format(v)} kn`;

export const ROUTE_NAME: Record<string, string> = {
  suez: "Via Suez",
  cape: "Via the Cape",
  direct: "Direct",
};

/** The difference line, said from the recommended route's side: "saves X SDR · −Y days".
 * The values are the difference row's (Cape − Suez); only the sign shown is chosen here, by a comparison. */
export function savingLine(recommended: "suez" | "cape", d: RouteDifference): string {
  const abs = fmt(2, "never");
  const absDays = fmt(2, "never");
  // the recommended route's cost / days relative to the other route have the sign of (other − recommended)
  const otherCostsMore = recommended === "suez" ? d.change_total_sdr > 0 : d.change_total_sdr < 0;
  const recommendedIsSlower = recommended === "suez" ? d.change_sea_days < 0 : d.change_sea_days > 0;
  const money =
    d.change_total_sdr === 0
      ? "costs the same"
      : otherCostsMore
        ? `saves ${abs.format(d.change_total_sdr)} SDR`
        : `costs ${abs.format(d.change_total_sdr)} SDR more`;
  const days =
    d.change_sea_days === 0
      ? "same days at sea"
      : `${recommendedIsSlower ? "+" : "−"}${absDays.format(d.change_sea_days)} days`;
  return `${money} · ${days}`;
}

/** The graph's node names (allow-listed by the API, ROUTE_NODES) in the words the progress stepper shows. */
export const ROUTE_STEPS: { node: string; label: string }[] = [
  { node: "inputs", label: "Checking the vessel" },
  { node: "routes", label: "Finding the routes" },
  { node: "costs", label: "Pricing fuel and dues" },
  { node: "context", label: "Reading traffic and news" },
  { node: "advisor", label: "Writing the advice" },
  { node: "validator", label: "Checking every number" },
  { node: "render", label: "Done" },
];

export const STATUS_NOTE: Record<string, string> = {
  ok: "",
  no_suez_on_route: "The Suez Canal is not on this voyage, so there is nothing to compare.",
  suez_only: "Only the Suez route exists for this voyage.",
  not_permitted: "Route advice is not part of your access.",
  no_data: "A port or the vessel was not found in the data.",
  output_invalid: "The advice could not be written in the checked shape, so it is not shown.",
  validation_failed: "The advice did not pass its number checks, so it is not shown.",
};

export const LOCODE = /^[A-Z]{2}[A-Z2-9]{3}$/;

export const VESSEL_TYPES = [
  "Chemical Tankers & Other Liquid Bulk Tankers",
  "Containerships",
  "Crude Oil Tankers",
  "Cruise Ships",
  "Dry Bulk Vessels",
  "General Cargo / Multi-Purpose / Heavy Lift Vessels",
  "Liquefied Natural Gas (LNG) Carriers",
  "Liquefied Petroleum Gas (LPG) Carriers",
  "Other Vessels",
  "Petroleum Product Tankers",
  "Roll-On/Roll-Off (Ro/Ro) Vessels",
  "Special Floating Units",
  "Vehicles Carriers",
] as const;

/** `route_advice:<employee>:<date>:<from>-<to>:<n>` → its readable parts (for the list; the id stays the key). */
export function threadParts(
  thread: string,
): { date: string; origin: string; destination: string; n: string } | null {
  const m = /^route_advice:\d+:(\d{4}-\d{2}-\d{2}):([A-Z0-9]{5})-([A-Z0-9]{5}):(\d+)$/.exec(thread);
  return m ? { date: m[1]!, origin: m[2]!, destination: m[3]!, n: m[4]! } : null;
}
