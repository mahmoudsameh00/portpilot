"""The `weekly_pack` LangGraph workflow (Agents plan §3, §5b, §5c): one report week → a validated deck draft → the
Finance manager's approval → the PortPilot PPTX saved.

Phase 6 (§5c): the Writer writes numbers as slots (`deck/slots.py`), code draws the fixed parts of the deck
(`deck/render.py`), the Validator binds every number to its field (`deck/validator.py`, V1–V7) and reads the rendered
file back (`deck/readback.py`, V8); a rewrite is a patch of the failing texts only (`DeckPatch`).

- The user and the dataset are the run context (`RunContext`, `context_schema`), passed on every invoke and resume,
  never kept in the state and never visible to a model (ADR-049).
- The state holds JSON-only values (tool results as `ToolResult.model_dump(mode="json")`, Pydantic outputs dumped),
  so every checkpoint is plain data and a resumed run reads exactly what the crashed one wrote.
- Deterministic nodes (P5-1): `readiness` (gate), `kpi`, `audit`, `validator`, `approval`, `publisher`. Agent steps:
  `insight_llm` ⇄ `insight_tools` (`ToolNode(STAGE1_TOOLS)`, which hands the run context to the tools), then
  `insight_notes` and `writer` (one structured call each). Every LLM call goes through `roles` (ADR-045 over llm.py).
- A node that is interrupted or crashes is re-run from its start on resume: `approval` does nothing before its
  `interrupt()`, and every node only returns state updates (the validator's preview and the publisher's files are
  safely replaced; publications retain immutable versions selected by an atomic manifest).

Evidence ids (`graphs/models.py`): `kpi.<dataset>`, `audit.week`, `audit.ytd` (weeks 1 … w, weekly-pack plan
Phase C), `insight.<tool_call_id>`.
"""
# pyright: reportTypedDictNotRequiredAccess=false
# (the state is total=False: a node runs only after the node that sets the keys it reads; LangGraph's config
#  always carries `configurable` — ADR-063 amendment 2)
import hashlib
import json
import operator
import re
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any, cast, Literal, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime
from langgraph.types import interrupt
from pydantic import ValidationError

from pipelines.agents import checkpointer, publications, skill_loader, traffic_claims
from pipelines.agents.deck import charts as charts_mod
from pipelines.agents.deck import readback, render, sample, slots
from pipelines.agents.deck import validator as v2
from pipelines.agents.graphs import models as m
from pipelines.agents.roles import FakeRoles, StructuredError
from pipelines.agents.tools import audit as audit_tool
from pipelines.agents.tools import context, db, external, finance, trust
from pipelines.agents.tools.context import RunContext
from pipelines.agents.tools.registry import STAGE1_TOOLS
from pipelines.lib.common import project_root

Status = Literal["running", "not_ready", "not_permitted", "output_invalid", "validation_failed", "awaiting_approval",
                 "rejected", "published"]
KPI_DATASETS = ("weekly", "category", "customers", "overdue", "trend")
RANKED_LIMIT = 10                      # customers / overdue rows handed to the agents (the deck shows a top 10)
MAX_TOOL_ROUNDS = 4                    # Insight tool rounds (P5-1); the last round has no tools bound
MAX_REWRITES = 2                       # Writer rewrites after a failed Validator, then stop (§3)
SEARCH_K = 3                           # passages per search_documents call in the pack (P5-8: Groq 8K TPM)
REPORT_YEAR = 2025                     # D12: replay of 2025's 52 ISO weeks
DRAFT_LABEL, APPROVED_LABEL = v2.DRAFT_LABEL, "Approved"
NUMERIC_TOOLS = slots.NUMERIC_TOOLS    # PortPilot's structured tools (ADR-049) + public structured context


class PackState(TypedDict, total=False):
    report_week: int
    status: Status
    stop_reason: str
    readiness: dict
    evidence: dict[str, dict]
    messages: Annotated[list[AnyMessage], add_messages]
    insight: dict
    draft: dict
    draft_origin: Literal["writer", "edit", "fallback", "revision"]
    degraded: dict                     # c4: what code replaced after the rewrites failed (shown to the approver)
    verdict: dict
    rewrites: int
    approval_log: Annotated[list[dict], operator.add]
    published: dict
    preview: dict | None               # the draft PPTX the approver opens: {path, sha256} (Phase 6)
    normalized: Annotated[list[str], operator.add]   # slot-form fixes made by code on the Writer's text (D-P7-14)
    charts: dict                       # approver-additions plan Phase C: chart → its variant (only non-default ones)
    # approver-additions plan Phase D (a "revise": the analysis changed, the deck drafted again)
    redrafted: bool                    # the current draft comes from a revise (D2: earlier edits / additions gone)
    steer_from: int                    # index of the approver's request in `messages`: tool rounds count from it
    pending_analysis: list[dict]       # the approver's note edits, applied to the notes a steered re-run returns
    revision: dict                     # what the last revise did (edits, steer, skipped edits, why it failed)
    before_revise: dict | None         # the pack before the revise: restored if the re-draft cannot be shown
    llm_usage: Annotated[list[dict], operator.add]


def _usage(node: str, reply) -> list[dict]:
    return [{"node": node, **c} for c in reply.calls]


# --- 1 Data Readiness -----------------------------------------------------------------------------------------------
# Gate before any agent step: the week must be complete enough to report. Reasons are written for the person who
# reads the stopped run. Non-gating facts (a warm-up week) are notes, not failures.

READINESS_SQL = {
    "kpi_row": "SELECT week_end, is_warmup FROM finance.kpi_weekly WHERE report_week = %s",
    "invoices": "SELECT count(*) AS n, "
                "count(*) FILTER (WHERE customer_id IS NULL OR due_date IS NULL OR amount_sdr IS NULL "
                "OR vessel_category IS NULL OR priced_condition IS NULL) AS key_nulls "
                "FROM finance.fact_invoice WHERE invoice_report_week = %s",
    "payments_through": "SELECT max(paid_date) AS d FROM finance.fact_payment",
}


def check_readiness(user, report_week: int) -> dict:
    """The gate's checks for one week (R1–R4 of §5b). Plain function: the node and the check script call it."""
    if not context.permitted(user, context.FINANCE_VIEWS):
        return {"ready": False, "permitted": False, "checks": {}, "reasons": ["not permitted (ADR-006)"],
                "notes": []}
    kpi_row = db.fetch(READINESS_SQL["kpi_row"], (report_week,))
    inv = db.fetch(READINESS_SQL["invoices"], (report_week,))[0]
    through = db.fetch(READINESS_SQL["payments_through"])[0]["d"]
    week_end = kpi_row[0]["week_end"] if kpi_row else None
    checks = {
        "R1_kpi_row": bool(kpi_row),
        "R2_invoices": inv["n"] > 0,
        "R3_key_nulls_zero": inv["key_nulls"] == 0,
        "R4_payments_through_as_of": bool(week_end and through and through >= week_end),
    }
    reasons = {
        "R1_kpi_row": f"finance.kpi_weekly has no row for week {report_week}",
        "R2_invoices": f"no invoice dated in week {report_week}",
        "R3_key_nulls_zero": f"{inv['key_nulls']} invoices of the week miss a key field (customer, due date, "
                             "amount, category, condition)",
        "R4_payments_through_as_of": f"payments are loaded only through {through}, before the as-of date {week_end}",
    }
    notes = []
    if kpi_row and kpi_row[0]["is_warmup"]:
        notes.append("warm-up week (1–13): receivables and DSO still building up since 2025-01-01")
    return {"ready": all(checks.values()), "permitted": True, "checks": checks,
            "reasons": [reasons[k] for k, ok in checks.items() if not ok], "notes": notes,
            "facts": {"invoices": inv["n"], "week_end": week_end.isoformat() if week_end else None,
                      "payments_through": through.isoformat() if through else None}}


def readiness(state: PackState, runtime: Runtime[RunContext]) -> dict:
    r = check_readiness(runtime.context.user, state["report_week"])
    status = "running" if r["ready"] else ("not_permitted" if not r["permitted"] else "not_ready")
    return {"readiness": r, "status": status, "evidence": {}, "rewrites": 0}


def after_readiness(state: PackState) -> str:
    return "kpi" if state["status"] == "running" else END


# --- 2 KPI ----------------------------------------------------------------------------------------------------------

def kpi_evidence(user, report_week: int, dataset: str = "live") -> dict[str, dict]:
    """`dataset` = the run context's: "test" reads the evaluation copy's twin views (migration 017, Phase 7)."""
    return {f"kpi.{d}": finance.finance_kpi(user, source=dataset, report_week=report_week, dataset=d,
                                            **({"limit": RANKED_LIMIT} if d in finance.RANKED else {})
                                            ).model_dump(mode="json")
            for d in KPI_DATASETS}


def link_evidence(user, report_week: int, dataset: str = "live") -> dict[str, dict]:
    """`context.link` (traffic-billing link plan Phase 4, M17): whether the weekly invoice count moves with Suez transits
    so far this year. PortPilot data (finance views, level 2), not an external source; its `context.` id puts it on
    slide 9 next to the transits it is measured against. A link means "moves with", never a cause (Validator V10)."""
    return {"context.link": finance.finance_kpi(user, source=dataset, report_week=report_week,
                                                dataset="traffic_link").model_dump(mode="json")}


def kpi(state: PackState, runtime: Runtime[RunContext]) -> dict:
    ctx = runtime.context
    return {"evidence": {**state.get("evidence", {}), **kpi_evidence(ctx.user, state["report_week"], ctx.dataset),
                         **link_evidence(ctx.user, state["report_week"], ctx.dataset)}}


# --- 3 Invoice Auditor ----------------------------------------------------------------------------------------------

def audit_evidence(user, report_week: int, dataset: str) -> dict[str, dict]:
    """The week's audit + the year to date (weeks 1 … w, slide 8 when the week has no finding: W-R4)."""
    return {"audit.week": audit_tool.invoice_audit(user, report_week=report_week, dataset=dataset)
            .model_dump(mode="json"),
            "audit.ytd": audit_tool.invoice_audit(user, report_week=report_week, dataset=dataset, through_week=True)
            .model_dump(mode="json")}


def audit(state: PackState, runtime: Runtime[RunContext]) -> dict:
    ctx = runtime.context
    return {"evidence": {**state["evidence"], **audit_evidence(ctx.user, state["report_week"], ctx.dataset)}}


# --- 3b External context (external-context plan, owner E1 / E3: fetched by code every week) -----------------------

NEWS_QUERY = "Suez Canal Red Sea shipping"   # E3: fixed, the week's dates; the same query + window = a cache hit
NEWS_RESULTS = 3
CONTEXT_WEEKS_BEFORE = 4                     # Suez transits: the report week and the four weeks before


def _week_dates(evidence: dict) -> tuple[date, date] | None:
    rows = (evidence.get("kpi.weekly") or {}).get("rows") or []
    if not rows or not rows[0].get("week_start") or not rows[0].get("week_end"):
        return None
    return date.fromisoformat(str(rows[0]["week_start"])[:10]), date.fromisoformat(str(rows[0]["week_end"])[:10])


def _unavailable(tool: str, why: str) -> dict:
    return {"tool": tool, "status": "context_unavailable", "rows": [], "source": None, "note": why[:300]}


def context_evidence(user, evidence: dict) -> dict[str, dict]:
    """`context.suez` and `context.news` for the report week, whatever the Insight model later chooses (W14,
    2026-11-07: it called no context tool and slide 9 said "External context unavailable"). Every outcome is kept as
    the tool returned it (ok / no_data / context_unavailable + its note); an exception becomes context_unavailable —
    the pack never stops for context. Public data (ADR-049: `PUBLIC_EXTERNAL`), so the evaluation copy fetches it too."""
    wk = _week_dates(evidence)
    if wk is None:
        why = "the week's dates are not in kpi.weekly"
        return {"context.suez": _unavailable("suez_transits", why), "context.news": _unavailable("web_search", why)}
    start, end = wk
    calls = {"context.suez": ("suez_transits", lambda: external.suez_transits(
                 user, start=start - timedelta(weeks=CONTEXT_WEEKS_BEFORE), end=end)),
             "context.news": ("web_search", lambda: external.web_search(
                 user, query=NEWS_QUERY, start_date=start, end_date=end, max_results=NEWS_RESULTS))}
    out = {}
    for eid, (tool, call) in calls.items():
        try:
            out[eid] = call().model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 — a source outage or a bad reply is context unavailable, stated
            out[eid] = _unavailable(tool, f"{type(exc).__name__}: {exc}")
    if out["context.suez"].get("status") == "ok":
        out["context.suez"] = {**out["context.suez"], **transit_week(out["context.suez"]["rows"], start, end)}
    return out


SUEZ_TOTALS = ("week_mean_transits", "week_min_transits", "week_min_date", "week_max_transits", "week_max_date",
               "prev4_mean_transits")


def transit_week(rows: list[dict], start: date, end: date) -> dict:
    """D-EC-4 (Phase C, 2026-11-08: the Writer summarised 35 daily rows itself — "between 28 and 45 a day" — and V2
    refused the wrong range every time): code computes the report week's mean / min / max (with their dates) and the
    mean of the four weeks before, as result-level fields the Writer cites as slots
    ({context.suez:week_mean_transits})."""
    def day(r):
        return date.fromisoformat(str(r["date"])[:10])
    week = [r for r in rows if start <= day(r) <= end and r.get("n_total") is not None]
    before = [r for r in rows if day(r) < start and r.get("n_total") is not None]
    if not week:
        return {}
    lo, hi = min(week, key=lambda r: r["n_total"]), max(week, key=lambda r: r["n_total"])
    return {"week_mean_transits": round(sum(r["n_total"] for r in week) / len(week), 1),
            "week_min_transits": lo["n_total"], "week_min_date": str(lo["date"])[:10],
            "week_max_transits": hi["n_total"], "week_max_date": str(hi["date"])[:10],
            "prev4_mean_transits": round(sum(r["n_total"] for r in before) / len(before), 1) if before else None}


FAKE_CONTEXT_NOTE = "fake models (a check run): no external context is fetched"


def no_context(user, evidence: dict) -> dict[str, dict]:
    """The checks' fetch (graphs built with `FakeRoles`): no network, no Tavily credit; the same shape as an outage."""
    return {"context.suez": _unavailable("suez_transits", FAKE_CONTEXT_NOTE),
            "context.news": _unavailable("web_search", FAKE_CONTEXT_NOTE)}


def make_external_context(fetch):
    def external_context(state: PackState, runtime: Runtime[RunContext]) -> dict:
        return {"evidence": {**state["evidence"], **fetch(runtime.context.user, state["evidence"])}}
    return external_context


# --- evidence digest (what the agents read) -------------------------------------------------------------------------
# Compact pipe tables instead of every row and field (P5-8: a Groq request must fit 8K tokens per minute). The full
# rows stay in the state: the Validator checks numbers against them, not against the digest.

DIGEST_FIELDS = {
    "kpi.weekly": None,                                               # one row: every field
    "kpi.category": ("vessel_category", "billed_sdr", "billed_wow_change_sdr", "billed_wow_pct", "budget_sdr",
                     "budget_variance_sdr", "budget_variance_pct", "invoices_billed", "invoices_prev"),
    # weekly-pack plan Phase B: slide 7's risk columns (M15, M16)
    "kpi.customers": ("rank_13w", "rank_13w_prev", "customer_name", "credit_rating", "billed_13w_sdr",
                      "share_13w_pct", "ar_sdr", "overdue_sdr", "ar_to_billed_13w_pct", "is_watchlist",
                      "ontime_13w_pct"),
    "kpi.overdue": ("rank_by_amount", "invoice_number", "customer_name", "amount_sdr", "days_past_due",
                    "aging_bucket"),
    "kpi.trend": ("trend_week_label", "billed_sdr", "budget_sdr", "budget_variance_pct"),
    "audit.week": ("invoice_number", "vessel_category", "check_code", "probable_cause", "billed_sdr", "expected_sdr",
                   "difference_sdr", "duplicate_of"),
    "audit.ytd": ("report_week", "invoice_number", "vessel_category", "check_code", "difference_sdr"),
    # external-context plan §2b: fetched by code; news rows keep their trust label (untrusted-content skill)
    "context.suez": ("date", "n_total"),
    "context.news": ("title", "published_date", "url", "snippet", "trust"),
    # traffic-billing link plan Phase 4: M17 of the report week (PortPilot data, computed in SQL)
    "context.link": ("report_week", "invoices_billed", "suez_transits_week", "n_weeks", "r_lag0", "r_lag1",
                     "r_threshold", "link", "link_lag"),
}
AUDIT_TOTALS = ("invoices_checked", "invoices_flagged", "amount_at_stake_sdr")


def _cell(v) -> str:
    return "" if v is None else str(v)


def digest(evidence: dict[str, dict], ids=None) -> str:
    parts = []
    for eid in ids or DIGEST_FIELDS:
        res = evidence.get(eid)
        if res is None:
            continue
        src = res.get("source") or {}
        head = f"[{eid}] {res['tool']} status={res['status']}"
        if src:
            head += f" source={src.get('name')} ({src.get('filter')})"
        if res.get("note"):
            head += f" note: {res['note']}"
        lines = [head]
        if eid in ("audit.week", "audit.ytd") and res["status"] == "ok":
            lines.append(" | ".join(f"{k}={_cell(res.get(k))}" for k in AUDIT_TOTALS))
        if eid == "context.suez" and res.get("week_mean_transits") is not None:    # D-EC-4: code's week summary
            lines.append(" | ".join(f"{k}={_cell(res.get(k))}" for k in SUEZ_TOTALS))
        rows = res.get("rows") or []
        fields = DIGEST_FIELDS.get(eid) or (tuple(rows[0]) if rows else ())
        if rows:
            if eid == "kpi.weekly":
                lines += [f"{k}={_cell(rows[0][k])}" for k in fields]
            else:
                lines.append(" | ".join(fields))
                lines += [" | ".join(_cell(r.get(k)) for k in fields) for r in rows]
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


# --- 4 Insight (agent with tools) -----------------------------------------------------------------------------------

INSIGHT_TASK = """You are the Insight agent of PortPilot's Weekly Finance Pack (ISO week {week} of {year}).
The KPI and invoice-audit results of the week are already fetched below, each with its evidence id, and so is the
week's external context (context.suez: Suez transits for the week and the four weeks before; context.news: that
week's news; context.link: whether billing has moved with those transits so far this year, computed in SQL — a
link means "moves with", never a cause) — do not fetch the same window again. Use your tools only for what is not there: a drill-down (another
window or query), or search_documents for a tariff rule (at most {k} passages). The
user's identity and access are handled by the system; never ask for them. When you have enough, answer with a short
plain-text summary of your findings and stop calling tools.

{skills}"""

NOTES_TASK = ("Now return the InsightNotes for week {week}: five summary bullets in the skill's order, at most three "
              "drivers, the external context kept apart, and the caveats. Every number copied exactly from a tool "
              "result, with the evidence ids it comes from — only ids from this list, never a tool name:\n{ids}")


def _week_label(evidence: dict) -> str:
    rows = evidence.get("kpi.weekly", {}).get("rows") or [{}]
    return rows[0].get("iso_week_label") or "?"


def _cap_search(msg: AIMessage) -> AIMessage:
    """search_documents in the pack returns at most SEARCH_K passages (P5-8), whatever k the model asked for. The
    reply is changed before it is stored, so the history the model sees next matches the tool result."""
    if not any(c["name"] == "search_documents" for c in msg.tool_calls):
        return msg
    calls = [{**c, "args": {**c["args"], "k": min(int(c["args"].get("k") or SEARCH_K), SEARCH_K)}}
             if c["name"] == "search_documents" else c for c in msg.tool_calls]
    return msg.model_copy(update={"tool_calls": calls})


def _tool_rounds(messages: list) -> int:
    return sum(1 for x in messages if isinstance(x, AIMessage) and x.tool_calls)


def _evidence_id(tool_call_id: str) -> str:
    return "insight." + re.sub(r"[^A-Za-z0-9_.:-]", "_", tool_call_id)


def _tool_evidence(messages: list) -> dict[str, dict]:
    out = {}
    for x in messages:
        if isinstance(x, ToolMessage):
            try:
                res = json.loads(x.content) if isinstance(x.content, str) else x.content
            except json.JSONDecodeError:
                res = None
            if not isinstance(res, dict) or "status" not in res:
                res = {"tool": x.name, "status": "context_unavailable", "rows": [], "source": None,
                       "note": f"tool error: {str(x.content)[:200]}"}
            out[_evidence_id(x.tool_call_id)] = res
    return out


def evidence_index(evidence: dict[str, dict], messages: list) -> str:
    """One line per evidence id: what it is. The model never sees its own tool-call ids, so without this list it
    cites tool names (seen in S6: "suez_transits" as an evidence id)."""
    calls = {_evidence_id(cast(str, c["id"])): c for x in messages if isinstance(x, AIMessage) for c in x.tool_calls}
    lines = []
    for eid, res in sorted(evidence.items()):
        what = (f"{calls[eid]['name']}({json.dumps(calls[eid]['args'], ensure_ascii=False)})" if eid in calls
                else res.get("tool"))
        keys = slots.row_keys(res) if len(res.get("rows") or []) > 1 else ()
        keyed = f", rows keyed by {'/'.join(keys)}" if keys else ""
        lines.append(f"- {eid}: {what}, status {res.get('status')}{keyed}")
    return "\n".join(lines)


def _stop(node: str, exc: Exception) -> dict:
    """A model that answered twice with an invalid object: re-running reads the same cached replies, so the run ends
    with a stated status (owner 2026-10-19); quota exhaustion is not caught — the thread waits at its checkpoint."""
    return {"status": "output_invalid", "stop_reason": f"{node}: {str(exc)[:400]}",
            "llm_usage": [{"node": node, **c} for c in getattr(exc, "calls", [])]}


def after_agent_step(nxt: str):
    def route(state: PackState) -> str:
        if state.get("status") == "output_invalid":
            return "revise_failed" if state.get("before_revise") else END   # a revise never loses a waiting pack
        return nxt
    return route


def make_insight_llm(roles):
    def insight_llm(state: PackState) -> dict:
        msgs = list(state.get("messages") or [])
        new = []
        if not msgs:
            skills = "\n\n".join(skill_loader.load(s) for s in ("weekly-variance-analysis", "untrusted-content"))
            new = [SystemMessage(INSIGHT_TASK.format(week=state["report_week"], year=REPORT_YEAR, k=SEARCH_K,
                                                     skills=skills)),
                   HumanMessage(digest(state["evidence"]))]
            msgs = new
        # a revise's steer gets its own tool rounds (counted from the approver's request; 0 = the whole history)
        tools = STAGE1_TOOLS if _tool_rounds(msgs[state.get("steer_from", 0):]) < MAX_TOOL_ROUNDS else None
        reply = roles.get("insight").invoke(msgs, tools=tools)
        ai = _cap_search(reply.message)
        return {"messages": [*new, ai], "llm_usage": _usage("insight_llm", reply),
                "evidence": {**state["evidence"], **_tool_evidence(state.get("messages") or [])}}
    return insight_llm


def after_insight_llm(state: PackState) -> str:
    last = state["messages"][-1]
    return "insight_tools" if isinstance(last, AIMessage) and last.tool_calls else "insight_notes"


def make_insight_notes(roles):
    def insight_notes(state: PackState) -> dict:
        evidence = {**state["evidence"], **_tool_evidence(state["messages"])}
        ask = HumanMessage(NOTES_TASK.format(week=state["report_week"],
                                             ids=evidence_index(evidence, state["messages"])))
        try:
            reply = roles.get("insight").structured([*state["messages"], ask], m.InsightNotes)
        except StructuredError as exc:
            return {**_stop("insight_notes", exc), "evidence": evidence}
        notes, extra = reply.parsed.model_dump(mode="json"), {}
        if state.get("pending_analysis"):           # a steered revise: the approver's edits on the new notes
            edited, why = apply_analysis(notes, state["pending_analysis"], evidence, state["report_week"])
            notes = notes if why else edited
            extra = {"pending_analysis": [], "revision": {**(state.get("revision") or {}),
                                                          "edits_applied": not why, "edits_skipped": why[:6]}}
        # D-TL-11: a refused traffic/billing sentence is replaced by the fixed M17 wording of the run's own verdict
        # (code, no model call, recorded in `normalized`) — one wording slip no longer costs the week's pack.
        notes, repaired = traffic_claims.repair_notes(notes, evidence)
        if repaired:
            extra = {**extra, "normalized": repaired}
        claim_errors = traffic_claims.note_problems(notes, evidence)
        if claim_errors:
            # What could not be repaired (no single measured verdict) stops before unsafe analysis reaches the
            # Writer or the review API. A revise uses its existing restore path; fresh runs stop explicitly.
            return {"status": "output_invalid", "stop_reason": "insight_notes V10: " + "; ".join(claim_errors)[:350],
                    "evidence": evidence, "llm_usage": _usage("insight_notes", reply), **extra}
        return {"insight": notes, "evidence": evidence, "llm_usage": _usage("insight_notes", reply), **extra}
    return insight_notes


# --- 5 Report Writer (Phase 6, §5c: slots, the code-drawn parts, the patch rewrite) ---------------------------------

SLOT_RULES = """Numbers: never type a PortPilot number. Write a slot; code fills it with the allowed rounding, the sign and
the unit, from the field you name:
  {{<evidence id>:<field>|<format>}}          one-row results (kpi.weekly) and result totals (audit.week)
  {{<evidence id>[<row>]:<field>|<format>}}   lists: <row> = the row's key value (the key is named in the evidence list)
Formats: money M (2 decimals, "M SDR"), k (1 decimal), sdr (as returned); percent %1 or %2; days and counts none.
Add |dir to a change field (wow, change, variance, difference) to write "up 3.2 %" / "down 1.07 M SDR".
A slot writes its own unit: never write SDR, % or days after a slot ("{{kpi.weekly:ar_sdr|M}} SDR" is wrong);
with |dir it also writes "up" / "down": no direction word right before it ("rose {{…|dir}}" is wrong).
Examples: "Billed {{kpi.weekly:billed_sdr|M}} in week {week}, {{kpi.weekly:billed_wow_pct|%1|dir}} WoW"
          "Cruise Ships billed {{kpi.category[Cruise Ships]:billed_wow_change_sdr|M|dir}} WoW"
          "{{audit.week:invoices_checked}} invoices checked, {{audit.week:invoices_flagged}} flagged"
A null field (no WoW in week 1) cannot be a slot: write "not available". Say what each number is (billed, collected,
AR, overdue, DSO, budget, share) and name its category, customer or invoice before it. Counts of things you write
yourself go in words ("three drivers"); the week and year may be digits."""

WRITER_TASK = """You are the Report Writer of PortPilot's Weekly Finance Pack. Write the deck for ISO week {week} of
{year} as a DeckDraft. Code draws the title slide, the KPI tiles, every table and chart and the sources slide; you
write only:
- title: "PortPilot Weekly Finance Pack — {label} — {draft}"
- slide_titles: one per slide 1 to 10, each stating the slide's finding (slide 1: the week's headline)
- bullets, slides 2 to 9 only: slide 2 exactly five (the executive summary); slides 3 to 8 at most three comments
  each; slide 9 the external context lines (or "External context unavailable"), never a PortPilot figure.
Evidence each slide may cite (the bullet's evidence_ids, and its slots): {slide_map}

{slot_rules}

{skills}"""

PATCH_TASK = """You are the Report Writer of PortPilot's Weekly Finance Pack (ISO week {week} of {year}). The Validator
refused the texts below in your draft. Return a DeckPatch with one fix per text: the whole corrected text and, for a
bullet, its evidence ids. Keep what was right; fix exactly the problems listed.
Evidence each slide may cite: {slide_map}

{slot_rules}"""


def _slide_map() -> str:
    return "; ".join(f"{s}: {', '.join(ids) or 'none (code)'}" for s, ids in v2.SLIDE_EVIDENCE.items())


def _writer_skills(evidence: dict) -> str:
    names = ["deck-style-guide", "number-validation"]
    if (evidence.get("audit.week") or {}).get("rows"):
        names.append("suez-toll-audit")
    return "\n\n".join(skill_loader.load(n) for n in names)


def _patchable(problems: list[dict]) -> bool:
    """A patch replaces texts; a wrong deck shape (V4: bullet counts, missing titles) needs the whole deck again."""
    return not any(p["rule"] == "V4" for p in problems)


def _fix_list(draft: dict, problems: list[dict]) -> tuple[str, list[str]]:
    """The failing texts with their problems grouped (the rewrite's whole feedback) and the evidence they may use."""
    groups: dict[tuple, list[str]] = {}
    for p in problems:
        if p.get("bullet") is not None:
            key = ("bullet", p["bullet"])
        elif p.get("slide") is not None:
            key = ("slide_title", p["slide"])
        else:
            key = ("title", 0)
        groups.setdefault(key, []).append(f"{p['rule']} {p.get('token') or ''}: {p['message']}".replace("  ", " "))
    titles = {t["slide"]: t["title"] for t in draft["slide_titles"]}
    lines, ids = [], set()
    for (target, idx), msgs in sorted(groups.items()):
        if target == "bullet":
            b = draft["bullets"][idx]
            text, cited = b["text"], list(b["evidence_ids"])
            lines.append(f"- target bullet, index {idx} (slide {b['slide']}), evidence_ids {cited}: "
                         f"{json.dumps(text, ensure_ascii=False)}")
        elif target == "slide_title":
            text, cited = titles.get(idx, ""), []
            lines.append(f"- target slide_title, index {idx}: {json.dumps(text, ensure_ascii=False)}")
        else:
            text, cited = draft["title"], []
            lines.append(f"- target title, index 0: {json.dumps(text, ensure_ascii=False)}")
        lines += [f"    problem {msg}" for msg in msgs]
        # the evidence this fix needs: what the text cites or slots, and what the problems point to (the hints)
        ids |= set(cited) | {s.eid for s in slots.find_slots(text)}
        ids |= set(re.findall(r"\b(?:kpi|audit|insight|context)\.[A-Za-z0-9_.:-]*[A-Za-z0-9_]", " ".join(msgs)))
    return "\n".join(lines), sorted(ids)


def merge_patch(draft: dict, patch: m.DeckPatch) -> dict:
    """The draft with the fixes applied; a fix to a text that does not exist is ignored (the Validator runs again on
    the whole deck)."""
    d = json.loads(json.dumps(draft))
    titles = {t["slide"]: t for t in d["slide_titles"]}
    for f in patch.fixes:
        if f.target == "bullet" and 0 <= f.index < len(d["bullets"]):
            d["bullets"][f.index]["text"] = f.text
            if f.evidence_ids:
                d["bullets"][f.index]["evidence_ids"] = f.evidence_ids
        elif f.target == "slide_title" and f.index in titles:
            titles[f.index]["title"] = f.text
        elif f.target == "title":
            d["title"] = f.text
    return d


def make_writer(roles):
    def writer(state: PackState) -> dict:
        ev = state["evidence"]
        verdict = state.get("verdict")
        rewrite = bool(verdict and not verdict["passed"] and state.get("draft_origin") == "writer")
        week, label = state["report_week"], _week_label(ev)
        index = "[evidence ids you may cite]\n" + evidence_index(ev, state.get("messages") or [])
        try:
            problems: list[dict] = cast(dict, verdict)["problems"] if rewrite else []   # rewrite => a failed verdict
            if rewrite and _patchable(problems):
                fixes, needed = _fix_list(state["draft"], problems)
                msgs = [SystemMessage(PATCH_TASK.format(week=week, year=REPORT_YEAR, slide_map=_slide_map(),
                                                        slot_rules=SLOT_RULES.format(week=week))),
                        HumanMessage("\n\n".join([f"[texts to fix]\n{fixes}", index,
                                                  digest(ev, [e for e in needed if e in ev])]))]
                reply = roles.get("writer").structured(msgs, m.DeckPatch)
                draft = merge_patch(state["draft"], reply.parsed)
            else:
                body = [digest(ev), digest(ev, [k for k in ev if k.startswith("insight.")]), index,
                        "[insight notes]\n" + json.dumps(state["insight"], ensure_ascii=False)]
                if rewrite:      # a wrong deck shape: the whole deck again, with the problems and the draft
                    body.append("[validator] your previous draft failed these checks; fix them and return the whole "
                                "deck:\n" + json.dumps(problems, ensure_ascii=False)
                                + "\n[previous draft]\n" + json.dumps(state["draft"], ensure_ascii=False))
                msgs = [SystemMessage(WRITER_TASK.format(week=week, year=REPORT_YEAR, label=label, draft=DRAFT_LABEL,
                                                         slide_map=_slide_map(),
                                                         slot_rules=SLOT_RULES.format(week=week),
                                                         skills=_writer_skills(ev))),
                        HumanMessage("\n\n".join(b for b in body if b))]
                reply = roles.get("writer").structured(msgs, m.DeckDraft)
                draft = reply.parsed.model_dump(mode="json")
        except StructuredError as exc:
            return _stop("writer", exc)
        draft, fixed = normalize_draft(draft, ev)
        return {"draft": draft, "draft_origin": "writer", "rewrites": state.get("rewrites", 0) + rewrite,
                "llm_usage": _usage("writer", reply), "normalized": fixed}
    return writer


def normalize_draft(draft: dict, evidence: dict) -> tuple[dict, list[str]]:
    """The slot-form fixes of `slots.normalize_text` on every Writer text (Phase 7, D-P7-14): a format the field
    does not allow, a key on a one-row result, a unit or direction word written twice. Numbers are untouched (code
    writes them); a human edit is not normalized (it is checked as written)."""
    d, fixed = json.loads(json.dumps(draft)), []
    for b in d["bullets"]:
        b["text"], f = slots.normalize_text(b["text"], evidence)
        fixed += f
        # a slot names its evidence: list it among the bullet's citations when the Writer left it out (c3, D-P7-15)
        missing = [s.eid for s in slots.find_slots(b["text"]) if s.eid not in (b.get("evidence_ids") or [])]
        if missing:
            b["evidence_ids"] = [*(b.get("evidence_ids") or []), *dict.fromkeys(missing)]
            fixed.append(f"bullet {b['text'][:40]!r}: evidence ids {sorted(set(missing))} added from its slots")
    for t in d["slide_titles"]:
        t["title"], f = slots.normalize_text(t["title"], evidence)
        fixed += f
    return d, fixed


# --- 6 Validator (Phase 6, §5c: V1–V7 on the draft, V8 on the rendered file) --------------------------------------
# `deck/validator.py` binds every number to its field; when the draft passes, the deck is rendered and read back
# (V8) and the preview the approver opens is saved. A V8 problem is a renderer fault, not the Writer's: the run stops.

def _preview_stem(thread_id: str | None) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", thread_id or "run")


def _preview_path(reports_dir: Path, thread_id: str | None, sha256: str) -> Path:
    # a new file per content (D-P8-17): the approver keeps the previous preview open in PowerPoint, which locks it,
    # so an edit must never write over it; the same content (a resume after a crash) gets the same name
    return reports_dir / "_drafts" / f"{_preview_stem(thread_id)}_{sha256[:10]}.pptx"


def _drop_previews(reports_dir: Path, thread_id: str | None, keep: Path | None = None) -> list[str]:
    """Remove this thread's previews (all passes, and the one-file name of before D-P8-17) except `keep`; a file
    still open in PowerPoint is left and named in the result (the next pass, publish or reject tries again)."""
    drafts, stem, locked = reports_dir / "_drafts", _preview_stem(thread_id), []
    if not drafts.is_dir():
        return locked
    for p in [*drafts.glob(f"{stem}_*.pptx"), drafts / f"{stem}.pptx"]:
        if p == keep or not p.is_file():
            continue
        try:
            p.unlink()
        except PermissionError:
            locked.append(p.name)
    return locked


def make_validator(reports_dir: Path):
    def validator(state: PackState, config: RunnableConfig) -> dict:
        week, ev = state["report_week"], state["evidence"]
        v = v2.validate(state["draft"], ev, week)
        out: dict[str, Any] = {"preview": None}          # a failing draft has no preview
        if v.passed:
            ch = state.get("charts")
            data = render.render(state["draft"], ev, state["readiness"], DRAFT_LABEL, ch)
            problems = readback.validate_pptx(data, state["draft"], ev, state["readiness"], DRAFT_LABEL, ch)
            if problems:
                v = m.Verdict(passed=False, problems=problems)
            else:
                sha = hashlib.sha256(data).hexdigest()
                path = _preview_path(reports_dir, config["configurable"].get("thread_id"), sha)
                path.parent.mkdir(parents=True, exist_ok=True)
                if not (path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == sha):
                    path.write_bytes(data)                   # a new name per content: never the file the approver has open
                out["preview"] = {"path": path.as_posix(), "sha256": sha}
                _drop_previews(reports_dir, config["configurable"].get("thread_id"), keep=path)
        waiting = v.passed or state.get("draft_origin") == "edit"
        return {**out, "verdict": v.model_dump(mode="json"), "status": "awaiting_approval" if waiting else "running"}
    return validator


def after_validator(state: PackState) -> str:
    problems = state["verdict"]["problems"]
    stop = "revise_failed" if state.get("before_revise") else "stop_failed"   # a revise restores the pack before it
    if any(p["rule"] == "V8" for p in problems):
        return stop                            # the renderer and its own read-back disagree: never shown or saved
    if state["verdict"]["passed"] or state.get("draft_origin") == "edit":
        return "approval"                      # a failed human edit goes back to the human, with the problems
    if state.get("draft_origin") == "fallback":
        return stop                            # code's own replacement failed too: nothing is shown or saved
    return "writer" if state.get("rewrites", 0) < MAX_REWRITES else "fallback"


def stop_failed(state: PackState) -> dict:
    return {"status": "validation_failed"}


# --- 6b Fallback (c4, plan 2026-10-30): the code-drawn parts always reach the approver --------------------------------
# A draft that still fails after its rewrites would publish nothing, and the audit table code drew from `audit.week`
# would be lost with the Writer's text. Code replaces only the failing texts with its own (deck/sample.py, valid by
# construction): a summary bullet by the code bullet of its position, a comment dropped, the context line by code's,
# a failing title by code's; the Writer's passing bullets stay. The result goes through the same Validator + V8.

def fallback_draft(draft: dict, problems: list[dict], week: int, evidence: dict) -> tuple[dict, dict]:
    """(the draft with code's texts in place of the failing ones, what was replaced / dropped)."""
    code = sample.slot_draft(week, evidence)
    code_by_slide: dict[int, list[dict]] = {}
    for b in code["bullets"]:
        code_by_slide.setdefault(b["slide"], []).append(b)
    bad_bullets = {p["bullet"] for p in problems if p.get("bullet") is not None}
    bad_slides = {p["slide"] for p in problems if p.get("bullet") is None and p.get("slide") is not None}
    shape = {p["slide"] for p in problems if p["rule"] == "V4" and p.get("slide") is not None}
    replaced, dropped, out = [], [], []
    position: dict[int, int] = {}
    for i, b in enumerate(draft["bullets"]):
        pos = position[b["slide"]] = position.get(b["slide"], -1) + 1
        if b["slide"] in shape:
            continue                                     # a wrong slide shape: that slide is code's below
        if i not in bad_bullets:
            out.append(b)
        elif b["slide"] in (2, 9) and pos < len(code_by_slide.get(b["slide"], [])):
            out.append(code_by_slide[b["slide"]][pos])
            replaced.append(i)
        else:
            dropped.append(i)
    for s in sorted(shape | ({9} if not any(b["slide"] == 9 for b in out) else set())):
        out = [b for b in out if b["slide"] != s] + code_by_slide.get(s, [])
    if len([b for b in out if b["slide"] == 2]) != len(code_by_slide[2]):
        out = [b for b in out if b["slide"] != 2] + code_by_slide[2]
        shape.add(2)
    titles = {t["slide"]: t for t in draft["slide_titles"]}
    code_titles = {t["slide"]: t for t in code["slide_titles"]}
    new_titles = [code_titles[s] if (s in bad_slides or s not in titles) else titles[s] for s in sorted(code_titles)]
    title_bad = any(p.get("slide") is None and p.get("bullet") is None for p in problems)
    fixed = {"title": code["title"] if title_bad else draft["title"], "slide_titles": new_titles,
             "bullets": sorted(out, key=lambda b: b["slide"])}
    return fixed, {"replaced_bullets": replaced, "dropped_bullets": dropped, "code_slides": sorted(shape),
                   "code_slide_titles": sorted(bad_slides & set(code_titles)), "code_title": title_bad,
                   "problems_before": len(problems)}


def fallback(state: PackState) -> dict:
    draft, degraded = fallback_draft(state["draft"], state["verdict"]["problems"], state["report_week"],
                                     state["evidence"])
    return {"draft": draft, "draft_origin": "fallback", "degraded": degraded}


# --- 7 Approval (human in the loop, P5-4) ---------------------------------------------------------------------------

def approver_check(employee_id: int) -> tuple[bool, str]:
    """A Finance manager or the CEO may decide (read from PostgreSQL at every decision)."""
    try:
        u = context.load_user(employee_id)
    except PermissionError:
        return False, f"unknown employee {employee_id}"
    if u.role == "ceo" or (u.role == "manager" and u.department == "Finance"):
        return True, f"{u.role} / {u.department}"
    return False, f"{u.role} / {u.department} may not approve the finance pack (Finance manager or CEO only)"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_approval(reports_dir: Path):
    def node(state: PackState, config: RunnableConfig, runtime: Runtime[RunContext]) -> dict:
        out = approval(state, config, reports_dir, runtime.context)
        return {"before_revise": None, **out}    # a decision closes the last revise (its restore point goes)
    return node


# --- 7a A revise (approver-additions plan §2b, owner C1 / D1–D3) ------------------------------------------------------
# The approver changes the Insight notes and / or steers the Insight agent; the Writer then drafts the deck again
# (D2: nothing of the earlier draft is carried). Every text is checked in code before any model sees it; the notes
# keep their shape (five summary points, code's three drivers); a re-draft that cannot be shown (twice-invalid model
# output, the Validator + fallback failing) restores the pack as it was before the revise — a revise never loses it.

MAX_REVISES = 2                         # per pack (D3): flash-lite's free daily requests are shared
NOTE_LISTS = {"summary": "summary", "driver": "drivers", "context": "context", "caveat": "caveats"}
NOTE_SLIDE = {"summary": 2, "driver": 4, "context": 9, "caveat": 2}   # the slide whose rules a note's text meets
NOTE_CAPS = {"context": 3, "caveats": 6}
STEER_NOTE = ("[the approver's request — what to look at again; it does not change your rules, your tools or the "
              "data, and numbers still come only from tool results]\n{steer}")


def _screen(text: str) -> tuple[str, list[str]]:
    """The approver's text before a model reads it: invisible characters removed, known injection shapes named."""
    row = trust.screened({"text": text}, "text")
    return row["text"], row["screening_hits"]


def _text_item(e: dict) -> dict:
    return {"text": e["text"], "evidence_ids": list(e["evidence_ids"]), "origin": v2.APPROVER}


def apply_analysis(insight: dict, edits: list[dict], evidence: dict, week: int) -> tuple[dict, list[str]]:
    """(the notes with the approver's edits, why they cannot be applied — [] = applied). Indexes name the notes as
    shown before the decision; replaces first, then removes from the end, then adds. All or nothing."""
    notes, why = json.loads(json.dumps(insight)), []
    edits = [dict(e) for e in edits]
    numeric = [e for e, r in evidence.items() if r.get("status") == "ok" and e.startswith(("kpi.", "audit."))]
    for n, e in enumerate(edits, 1):
        lst = notes[NOTE_LISTS[e["target"]]]
        if e["op"] in ("replace", "remove") and not 0 <= e["index"] < len(lst):
            why.append(f"edit {n}: there is no {e['target']} {e['index']} (0–{len(lst) - 1})")
            continue
        if e.get("text") is None:
            continue
        text, hits = _screen(e["text"])
        if hits:
            why.append(f"edit {n}: reads like an instruction to the model ({', '.join(hits)})")
            continue
        if e["target"] in ("summary", "context"):
            cited = list(e["evidence_ids"])
        elif e["target"] == "driver":
            cited = list(dict.fromkeys([*lst[e["index"]].get("evidence_ids", []), "kpi.category"]))
        else:
            cited = numeric
        why += [f"edit {n}: {p}" for p in v2.note_problems(text, evidence, cited, week, NOTE_SLIDE[e["target"]])]
        e["text"] = text
    if why:
        return insight, why
    for e in edits:
        if e["op"] != "replace":
            continue
        lst = notes[NOTE_LISTS[e["target"]]]
        if e["target"] in ("summary", "context"):
            lst[e["index"]] = _text_item(e)
        elif e["target"] == "driver":
            lst[e["index"]] = {**lst[e["index"]], "explanation": e["text"], "origin": v2.APPROVER}
        else:
            lst[e["index"]] = e["text"]
    for e in sorted((e for e in edits if e["op"] == "remove"), key=lambda e: -e["index"]):
        del notes[NOTE_LISTS[e["target"]]][e["index"]]
    for e in edits:
        if e["op"] == "add":
            notes[NOTE_LISTS[e["target"]]].append(_text_item(e) if e["target"] == "context" else e["text"])
    for key, cap in NOTE_CAPS.items():
        if len(notes[key]) > cap:
            return insight, [f"at most {cap} {key} items, the edits make {len(notes[key])}"]
    return notes, []


def revise_failed(state: PackState) -> dict:
    """The re-draft of a revise could not be shown: the pack goes back to what the approver had (then the
    validator redraws its preview, no model call) with the reason."""
    why = state.get("stop_reason") or "the new draft failed the Validator after its rewrites and the code fallback"
    before = cast(dict, state.get("before_revise"))
    return {**before, "before_revise": None, "stop_reason": "", "status": "awaiting_approval",
            "revision": {**(state.get("revision") or {}), "failed": why[:300]},
            "approval_log": [{"at": _now(), "outcome": "revise_failed", "reason": why[:300]}]}


def revise(state: PackState, d: m.ApprovalDecision, entry: dict, ctx: RunContext, refused) -> dict:
    done = sum(1 for e in state.get("approval_log") or [] if e.get("outcome") == "revised")
    if done >= MAX_REVISES:
        return refused(f"at most {MAX_REVISES} revisions per pack (the free model quota is shared): edit, approve "
                       "or reject")
    edits = [e.model_dump() for e in d.analysis_edits]
    notes, why = apply_analysis(state["insight"], edits, state["evidence"], state["report_week"])
    if why:
        return refused("the analysis edits: " + "; ".join(why[:4]))
    steer = None
    if d.steer:
        steer, hits = _screen(d.steer)
        if hits:
            return refused(f"the steer reads like an instruction to the model ({', '.join(hits)}): say what to look "
                           "at, e.g. 'collections by customer'")
    new_charts, fetched, chart_log, why_c = chart_changes(cast(PackState, {**state, "charts": {}}), d.charts, ctx)
    if why_c:                          # D2: a revise starts from the default charts
        return refused(why_c)
    before = {k: state.get(k) for k in ("draft", "insight", "charts", "draft_origin", "degraded", "rewrites",
                                        "redrafted", "verdict")}
    logged = {"analysis_edits": edits, **({"steer": steer} if steer else {}),
              **({"charts": chart_log} if chart_log else {})}
    out: dict[str, Any] = {
        "approval_log": [{**entry, "outcome": "revised", **logged}], "charts": new_charts, "redrafted": True,
        "draft_origin": "revision", "rewrites": 0, "degraded": None, "before_revise": before, "status": "running",
        "revision": {"edits": len(edits), "steer": bool(steer)}}
    if fetched:
        out["evidence"] = {**state["evidence"], **fetched}
    if steer:                          # the Insight agent looks again; the edits wait for its new notes
        out.update(messages=[HumanMessage(STEER_NOTE.format(steer=steer))], steer_from=len(state["messages"]),
                   pending_analysis=edits)
    else:
        out["insight"] = notes
    return out


def chart_changes(state: PackState, changes: list[m.ChartChoice], ctx: RunContext) -> tuple[dict, dict, list, str]:
    """Owner C2: (the charts after the changes — non-default only, the evidence fetched for them, the log, the reason
    of a refusal or ""). A change overlays the chart's current variant; a window longer than 13 weeks makes code call
    `finance_kpi(trend, week − 13)` **as the run's user** (ADR-050 P5-5: never the approver's identity)."""
    week, out, fetched, log = state["report_week"], dict(state.get("charts") or {}), {}, []
    for c in changes:
        choice = {**(out.get(c.chart) or charts_mod.DEFAULTS[c.chart]), **c.model_dump(exclude_none=True)}
        why = charts_mod.problems(choice, week)
        if why:
            return {}, {}, [], f"the {c.chart} chart: {'; '.join(why)}"
        if charts_mod.needs_previous_trend(choice) and "kpi.trend_prev" not in state["evidence"]:
            res = finance.finance_kpi(ctx.user, source=ctx.dataset, report_week=week - 13, dataset="trend")
            if res.status != "ok":
                return {}, {}, [], f"the {c.chart} chart: the weeks before week {week - 12} are not available ({res.status})"
            fetched["kpi.trend_prev"] = res.model_dump(mode="json")
        full = charts_mod.resolve(choice)
        if charts_mod.is_default(full):
            out.pop(c.chart, None)
        else:
            out[c.chart] = full
        log.append(full)
    return out, fetched, log, ""


def approval(state: PackState, config: RunnableConfig, reports_dir: Path, ctx: RunContext) -> dict:
    ctx.check_active()
    audit_res = state["evidence"].get("audit.week", {})
    raw = interrupt({
        "thread_id": config["configurable"].get("thread_id"), "report_week": state["report_week"],
        "draft": state["draft"], "verdict": state["verdict"], "readiness_notes": state["readiness"]["notes"],
        # what the approver reads: the slots filled; the PPTX preview exists only for a passing draft
        "draft_rendered": v2.render_draft(state["draft"], state["evidence"]), "preview": state.get("preview"),
        "audit": {k: audit_res.get(k) for k in AUDIT_TOTALS},
        "degraded": state.get("degraded"),       # c4: the texts code put in place of the Writer's failing ones
        "charts": state.get("charts") or {},     # the approver's chart variants so far (plan Phase C)
        # plan Phase D: the analysis behind the deck (what a revise changes) and whether the deck was drafted again
        "insight": state.get("insight"), "redrafted": bool(state.get("redrafted")),
        "revision": state.get("revision"),
        "decisions": ["approve", "edit", "reject"] if state["verdict"]["passed"] else ["edit", "reject"]})
    entry = {"at": _now(), "decision": None, "approver_employee_id": None}

    def refused(why: str) -> dict:
        return {"approval_log": [{**entry, "outcome": "refused", "reason": why}], "status": "awaiting_approval"}

    try:
        d = m.ApprovalDecision.model_validate(raw)
    except ValidationError as exc:
        return refused(f"invalid decision: {exc.errors()[0]['msg']}")
    entry.update(decision=d.decision, approver_employee_id=d.approver_employee_id, comment=d.comment)
    ok, who = approver_check(d.approver_employee_id)
    if not ok:
        return refused(who)
    entry["approver"] = who
    # approver-additions plan: the models accept the new kinds since Phase A; each is enabled with its phase (B
    # additions, C charts, D revise) — until then a clear refusal, never a half-applied decision
    if d.decision == "revise":
        return revise(state, d, entry, ctx, refused)
    if d.decision == "approve":
        if not state["verdict"]["passed"]:
            return refused("the draft fails the Validator: edit or reject it")
        return {"approval_log": [{**entry, "outcome": "approved"}], "status": "awaiting_approval"}
    if d.decision == "reject":
        _drop_previews(reports_dir, config["configurable"].get("thread_id"))   # D9: save only what is approved
        return {"approval_log": [{**entry, "outcome": "rejected"}], "status": "rejected", "preview": None}
    bullets = state["draft"]["bullets"]
    bad = [e.bullet for e in d.edits if e.bullet >= len(bullets)]
    if bad:
        return refused(f"no bullet {bad} in the draft (0–{len(bullets) - 1})")
    new = [dict(b) for b in bullets]
    diff = []
    for e in d.edits:
        diff.append({"bullet": e.bullet, "slide": new[e.bullet]["slide"], "before": new[e.bullet]["text"],
                     "after": e.text})
        new[e.bullet]["text"] = e.text
    # owner B2: the approver's new bullets — placed by code after the slide's last bullet, checked like an edit
    have = {s: sum(1 for b in new if b["slide"] == s and b.get("origin") == v2.APPROVER) for s in v2.ADDITION_SLIDES}
    for a in d.additions:
        if a.slide not in v2.ADDITION_SLIDES:
            return refused(f"an addition goes on slides {v2.ADDITION_SLIDES[0]}–{v2.ADDITION_SLIDES[-1]} (comments "
                           f"and context), not on slide {a.slide}: slide 2 keeps its five points, 1 and 10 are code's")
        have[a.slide] += 1
        if have[a.slide] > v2.MAX_ADDITIONS:
            return refused(f"at most {v2.MAX_ADDITIONS} additions on slide {a.slide}")
    new_charts, fetched, chart_log, why = chart_changes(state, d.charts, ctx)
    if why:
        return refused(why)
    evidence = {**state["evidence"], **fetched}
    added = []
    for a in d.additions:
        at = max((i + 1 for i, b in enumerate(new) if b["slide"] <= a.slide), default=0)
        new.insert(at, {"slide": a.slide, "text": a.text, "origin": v2.APPROVER,
                        "evidence_ids": v2.addition_evidence(evidence, a.slide)})
        added.append({"slide": a.slide, "text": a.text})
    # D-B1: an addition must fit on its slide (the renderer's own estimate); else the approver shortens it or a
    # Writer comment (an edit in the same decision)
    if d.additions:
        full = sorted(set(render.comment_overflow({**state["draft"], "bullets": new}, evidence, state["readiness"],
                                                  DRAFT_LABEL, new_charts)) & {a.slide for a in d.additions})
        if full:
            return refused(f"no room on slide {', '.join(map(str, full))} for the addition: shorten it, or shorten "
                           "a comment of the slide with an edit in the same decision")
    logged = {"diff": diff, **({"added": added} if added else {}), **({"charts": chart_log} if chart_log else {})}
    return {"approval_log": [{**entry, "outcome": "edited", **logged}], "charts": new_charts,
            **({"evidence": evidence} if fetched else {}),
            "draft": {**state["draft"], "bullets": new}, "draft_origin": "edit", "status": "awaiting_approval"}


def after_approval(state: PackState) -> str:
    outcome = state["approval_log"][-1]["outcome"]
    if outcome == "revised":           # a steer → the Insight agent looks again; note edits only → the Writer
        return "insight_llm" if state["approval_log"][-1].get("steer") else "writer"
    return {"approved": "publisher", "rejected": END, "edited": "validator", "refused": "approval"}[outcome]


# --- 8 Publisher (save only, D9) ------------------------------------------------------------------------------------

def store_approved(week: int, thread_id: str, charts: dict | None, summary: list[str], approved: dict | None,
                   degraded: bool) -> None:
    """Migration 024 (approver-request plan §2c, owner R1): the approved pack's chart choices (defaults filled in)
    and summary lines, for the Power BI "Approved pack" page; a re-published week replaces its rows (the summary
    goes with them: ON DELETE CASCADE). Login ports_agent (agent_writer, 016's default privileges)."""
    t = charts_mod.resolve((charts or {}).get("trend") or charts_mod.DEFAULTS["trend"])
    v = charts_mod.resolve((charts or {}).get("variance") or charts_mod.DEFAULTS["variance"])
    with checkpointer.pool().connection() as conn, conn.transaction():
        conn.execute("DELETE FROM agent_state.pack_approved WHERE report_week = %s", (week,))
        conn.execute(
            "INSERT INTO agent_state.pack_approved (report_week, thread_id, approved_at, approver_employee_id, "
            "trend_series, trend_weeks, variance_measure, variance_rows, degraded) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (week, thread_id, (approved or {}).get("at") or _now(), (approved or {}).get("approver_employee_id"),
             list(t["series"]), t["weeks"], v["measure"], v["rows"], degraded))
        for i, text in enumerate(summary):
            conn.execute("INSERT INTO agent_state.pack_approved_summary (report_week, idx, text) VALUES (%s, %s, %s)",
                         (week, i, text))


def is_live_reports(reports_dir: Path) -> bool:
    """Only a pack published to the real `reports/` folder goes to the database: the checks publish to temp folders."""
    return reports_dir.resolve() == (project_root() / "reports").resolve()


def store_publication(run: dict) -> None:
    """Reconcile only the approved payload captured in the immutable publication, never current graph state."""
    if run.get("dataset") != "live":
        raise ValueError("only a live publication may synchronize approved finance rows")
    store_approved(run["report_week"], run["thread_id"], run.get("charts"), run["summary"], run.get("approved"),
                   bool(run.get("degraded")))


def make_publisher(reports_dir: Path):
    def publisher(state: PackState, config: RunnableConfig, runtime: Runtime[RunContext]) -> dict:
        runtime.context.check_active()
        week = state["report_week"]
        folder = reports_dir / f"{REPORT_YEAR}-W{week:02d}"
        draft = {**state["draft"], "title": state["draft"]["title"].replace(DRAFT_LABEL, APPROVED_LABEL)}
        u, usage = runtime.context.user, state.get("llm_usage") or []
        run = {"thread_id": config["configurable"].get("thread_id"), "report_week": week,
               "dataset": runtime.context.dataset,
               "run_as": {"employee_id": u.employee_id, "role": u.role, "department": u.department},
               "readiness": state["readiness"], "verdict": state["verdict"], "rewrites": state.get("rewrites", 0),
               "sources": {eid: res.get("source") for eid, res in sorted(state["evidence"].items())},
               "llm_calls": len(usage), "llm_cached": sum(c["cached"] for c in usage),
               "max_total_tokens": max((c["total_tokens"] or 0 for c in usage), default=0),
               "models": sorted({c["model"] for c in usage if c["outcome"] == "ok"}),
               # D-P7-14: every slot-form fix code made on the Writer's text stays visible (report: form_fixes)
               "normalized": state.get("normalized") or [],
               "degraded": state.get("degraded"),
               # external-context plan §2c: what the code fetched for slide 9, so an "unavailable" has its reason
               "external_context": {eid: {"status": res.get("status"), "note": res.get("note")}
                                    for eid, res in sorted(state["evidence"].items())
                                    if eid.startswith("context.") and eid != "context.link"},
               # traffic-billing link plan Phase 4: M17 is PortPilot data, recorded on its own
               "traffic_link": next(iter((state["evidence"].get("context.link") or {}).get("rows") or []), None)}
        # the approved deck: rendered with "Approved", read back (V8) before it is saved — never a file that differs
        ch = state.get("charts")
        if ch:
            run["charts"] = ch                     # what the approver chose to draw (plan Phase C)
        # approver-request plan §2c: the approved executive summary as the deck says it (slots filled) and who
        # approved — the dashboard's "this week's pack" reads the files, which outlive the 30-day thread retention
        shown = v2.render_draft(draft, state["evidence"])
        run["summary"] = [b["text"] for b in shown["bullets"] if b["slide"] == 2]
        run["approved"] = next(({"at": e["at"], "approver_employee_id": e.get("approver_employee_id")}
                                for e in reversed(state.get("approval_log") or []) if e.get("outcome") == "approved"),
                               None)
        data = render.render(draft, state["evidence"], state["readiness"], APPROVED_LABEL, ch)
        problems = readback.validate_pptx(data, draft, state["evidence"], state["readiness"], APPROVED_LABEL, ch)
        if problems:
            raise RuntimeError(f"the approved deck fails its read-back (V8): {problems[:3]}")
        run["deck_sha256"] = hashlib.sha256(data).hexdigest()
        runtime.context.check_active()
        files = {"deck_draft.json": draft, "approval.json": state["approval_log"], "run.json": run}
        payload = {name: publications.encoded(obj) for name, obj in files.items()} | {"deck.pptx": data}
        key = publications.digest(publications.encoded({"draft": draft, "approval": state["approval_log"],
                                  "evidence": state["evidence"], "run": {k: v for k, v in run.items() if k != "deck_sha256"}}))
        manifest, version_folder = publications.publish(folder, payload, key,
            store_publication if runtime.context.dataset == "live" and is_live_reports(reports_dir) else None,
            runtime.context.check_active)
        sync = manifest["db_sync"]["status"]
        db_rows = {"synced": "stored", "pending": "pending reconciliation",
                   "not_required": "skipped (not the live reports folder)"}[sync]
        _drop_previews(reports_dir, config["configurable"].get("thread_id"))
        drafts = reports_dir / "_drafts"
        if drafts.is_dir() and not any(drafts.iterdir()):
            shutil.rmtree(drafts)
        return {"status": "published", "draft": draft, "preview": None,
                "published": {"folder": version_folder.as_posix(), "week_folder": folder.as_posix(),
                              "publication_id": manifest["publication_id"], "files": sorted(payload), "at": manifest["at"],
                              "db_rows": db_rows, "db_sync": sync}}
    return publisher


# --- graph ----------------------------------------------------------------------------------------------------------

def build_graph(roles: Any, checkpointer=None, reports_dir: Path | None = None, use_fallback: bool = True,
                context_fetch=None):
    """The compiled workflow; `roles` = `roles.Roles()` (real models) or `roles.FakeRoles(script)` (checks).
    `use_fallback=False` (the evaluation's before-c4 side only) stops a draft that fails its rewrites, as before c4.
    `context_fetch(user, evidence)` = the external context's source: `context_evidence` (default), `no_context` by
    default for `FakeRoles` (a check never spends a Tavily credit), or a check's own stub."""
    if context_fetch is None:
        context_fetch = no_context if isinstance(roles, FakeRoles) else context_evidence
    g = StateGraph(PackState, context_schema=RunContext)
    g.add_node("readiness", readiness)
    g.add_node("kpi", kpi)
    g.add_node("audit", audit)
    g.add_node("external_context", make_external_context(context_fetch))
    g.add_node("insight_llm", make_insight_llm(roles))
    g.add_node("insight_tools", ToolNode(STAGE1_TOOLS))
    g.add_node("insight_notes", make_insight_notes(roles))
    g.add_node("writer", make_writer(roles))
    reports_dir = reports_dir or project_root() / "reports"
    g.add_node("validator", make_validator(reports_dir))
    g.add_node("stop_failed", stop_failed)
    g.add_node("revise_failed", revise_failed)
    g.add_node("fallback", fallback if use_fallback else stop_failed)   # False: the evaluation's before-c4 side
    g.add_node("approval", cast(Any, make_approval(reports_dir)))   # (state, config, runtime): as the publisher
    g.add_node("publisher", cast(Any, make_publisher(reports_dir)))
    g.add_edge(START, "readiness")
    g.add_conditional_edges("readiness", after_readiness, ["kpi", END])
    g.add_edge("kpi", "audit")
    g.add_edge("audit", "external_context")
    g.add_edge("external_context", "insight_llm")
    g.add_conditional_edges("insight_llm", after_insight_llm, ["insight_tools", "insight_notes"])
    g.add_edge("insight_tools", "insight_llm")
    g.add_conditional_edges("insight_notes", after_agent_step("writer"), ["writer", "revise_failed", END])
    g.add_conditional_edges("writer", after_agent_step("validator"), ["validator", "revise_failed", END])
    g.add_conditional_edges("validator", after_validator,
                            ["approval", "writer", "fallback", "stop_failed", "revise_failed"])
    g.add_edge("revise_failed", "validator")
    g.add_edge("fallback", "validator" if use_fallback else END)
    g.add_edge("stop_failed", END)
    g.add_conditional_edges("approval", after_approval,
                            ["publisher", "validator", "approval", "writer", "insight_llm", END])
    g.add_edge("publisher", END)
    return g.compile(checkpointer=checkpointer)
