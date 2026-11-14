// The weekly-pack decision rules, mirrored in the browser for early messages (Frontend plan §6.4, approver plan D1).
// The API and the graph stay authoritative; tests/decision.logic.spec.ts runs these rules on the cases exported from
// the API's own DecisionIn (tools/export_approval_cases.py), so the two sides cannot drift.
import type { DecisionIn } from "@/api/generated/client";

export type Limits = {
  max_chart_changes: number;
  max_analysis_edits: number;
  max_steer_chars: number;
  max_addition_chars: number;
};

const ANALYSIS_OPS: Record<string, readonly string[]> = {
  summary: ["replace"],
  driver: ["replace"],
  context: ["replace", "remove", "add"],
  caveat: ["replace", "remove", "add"],
};
const CHART_OPTIONS: Record<string, readonly string[]> = {
  trend: ["series", "weeks"],
  variance: ["measure", "rows"],
};
const FIELDS = new Set(["decision", "edits", "additions", "charts", "analysis_edits", "steer", "comment"]);

/** null = acceptable; otherwise the first problem, in the user's words. */
export function decisionProblem(body: Record<string, unknown>, limits: Limits): string | null {
  const unknown = Object.keys(body).find((k) => !FIELDS.has(k));
  if (unknown) return `"${unknown}" is not part of a decision`;
  const d = body as unknown as DecisionIn;
  const edits = d.edits ?? [];
  const additions = d.additions ?? [];
  const charts = d.charts ?? [];
  const analysis = d.analysis_edits ?? [];
  const steer = d.steer ?? null;
  if (steer !== null && (steer.length < 1 || steer.length > limits.max_steer_chars))
    return `the steer is at most ${limits.max_steer_chars} characters`;
  if (additions.some((a) => a.text.length > limits.max_addition_chars))
    return `an addition is at most ${limits.max_addition_chars} characters`;
  if (charts.length > limits.max_chart_changes) return `at most ${limits.max_chart_changes} chart changes`;
  if (analysis.length > limits.max_analysis_edits)
    return `at most ${limits.max_analysis_edits} analysis edits`;
  for (const c of charts) {
    const options = CHART_OPTIONS[c.chart] ?? [];
    const given = (["series", "weeks", "measure", "rows"] as const).filter(
      (k) => c[k] !== undefined && c[k] !== null,
    );
    if (given.some((k) => !options.includes(k))) return `the ${c.chart} chart has no such option`;
    if (given.length === 0) return `a ${c.chart} change names at least one option`;
  }
  for (const a of analysis) {
    if (!(ANALYSIS_OPS[a.target] ?? []).includes(a.op))
      return `${a.target}: only ${ANALYSIS_OPS[a.target]?.join(", ")}`;
    const indexed = a.op === "replace" || a.op === "remove";
    if (indexed !== (a.index !== undefined && a.index !== null))
      return "an index is given exactly for replace / remove";
    if ((a.op !== "remove") !== (a.text !== undefined && a.text !== null))
      return "a text is given exactly for replace / add";
  }
  const text = edits.length > 0 || additions.length > 0;
  const analysisChange = analysis.length > 0 || steer !== null;
  if (d.decision === "edit" && !(text || charts.length))
    return "an edit carries text edits, additions or chart changes";
  if (d.decision === "edit" && analysisChange) return "analysis edits and a steer belong to a revise";
  if (d.decision === "revise" && !analysisChange) return "a revise carries analysis edits and / or a steer";
  if (d.decision === "revise" && text)
    return "a revise drafts the deck again: text edits and additions go in a later edit";
  if ((d.decision === "approve" || d.decision === "reject") && (text || analysisChange || charts.length))
    return `${d.decision} carries no changes`;
  if (new Set(charts.map((c) => c.chart)).size !== charts.length) return "one change per chart";
  return null;
}
