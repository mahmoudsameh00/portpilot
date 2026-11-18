"""External context check (external-context plan §3, Phase B): the week's Suez transits and news are fetched by code.

Plan:    docs/plans/Pack_external_context_plan.md (APPROVED 2026-11-08, owner E1–E5).
Run:     uv run python tools/run.py pipelines/scripts/agents/External_context_check.py  (from the project root)

Reads:   PostgreSQL read-only (PG_RO_USER): employees, the finance and audit views of one week. No LLM call (scripted
         fake models) and no network: the context fetch is a stub passed to `build_graph(context_fetch=…)`.
Writes:  a throw-away temp folder for previews / the published pack; checkpoints in memory (InMemorySaver).
Re-run:  safe.

Phases
1. The fetch, run by code: with an Insight that calls no tool, `context.suez` / `context.news` are in the evidence,
   in the Insight's first message (the digest, news rows with their trust label) and in the Writer's; the prompt says
   not to fetch the same window again; the fetch runs once per pack — a steered revise does not fetch again.
2. An outage: a fetch that raises → `context_unavailable` with the reason in the state and, once published, in
   `run.json` `external_context`; the pack is not stopped. The checks' default (`FakeRoles` → `no_context`) fetches
   nothing; the real default is `context_evidence`.
3. Evidence rules: `context.*` ids pass `EVIDENCE_ID`; slide 9 (and 2) may cite them, slide 3 may not.
Final Checkpoint.
"""
# %% Setup
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from pipelines.agents import roles  # noqa: E402
from pipelines.agents.deck import sample  # noqa: E402
from pipelines.agents.deck import validator as v2  # noqa: E402
from pipelines.agents.graphs import models as m  # noqa: E402
from pipelines.agents.graphs import weekly_pack as wp  # noqa: E402
from pipelines.agents.tools import context, db  # noqa: E402
from pipelines.lib import common  # noqa: E402

common.load_env(ROOT)
DONE: list[int] = []
W = 23
FIN_MGR = db.fetch("SELECT e.employee_id FROM employees e JOIN roles r USING (role_id) JOIN departments d "
                   "USING (department_id) WHERE r.role_name = 'manager' AND d.department_name = 'Finance' "
                   "ORDER BY e.employee_id LIMIT 1")[0]["employee_id"]
user = context.load_user(FIN_MGR)
EV = {**wp.kpi_evidence(user, W), **wp.audit_evidence(user, W, "live")}
REPORTS = Path(tempfile.mkdtemp(prefix="external_context_check_"))

SUEZ_ROWS = [{"date": f"2025-05-{d:02d}", "n_total": 30 + d % 7} for d in range(1, 36) if d <= 31] + \
            [{"date": f"2025-06-0{d}", "n_total": 33} for d in range(1, 5)]
NEWS_ROWS = [{"title": "Carriers weigh a return to the Suez route", "url": "https://example.org/a",
              "published_date": "2025-06-04", "snippet": "Shipping lines said they may resume transits.",
              "trust": "web_content"}]


class Fetch:
    """A context fetch that counts its calls: ok rows, or an exception (an outage)."""

    def __init__(self, fail=False):
        self.fail, self.calls = fail, 0

    def __call__(self, user, evidence):
        self.calls += 1
        if self.fail:
            raise TimeoutError("PortWatch did not answer")
        return {"context.suez": {"tool": "suez_transits", "status": "ok", "rows": SUEZ_ROWS, "note": "IMF PortWatch",
                                 "source": {"kind": "api", "name": "portwatch", "filter": "test"}},
                "context.news": {"tool": "web_search", "status": "ok", "rows": NEWS_ROWS, "note": None,
                                 "source": {"kind": "api", "name": "tavily", "filter": "test"}}}


def failing_fetch(fetch: Fetch):
    """The node's own guard is inside `context_evidence`; a stub that raises is wrapped the same way here."""
    def call(user, evidence):
        try:
            return fetch(user, evidence)
        except Exception as exc:  # noqa: BLE001
            why = f"{type(exc).__name__}: {exc}"
            return {"context.suez": wp._unavailable("suez_transits", why),
                    "context.news": wp._unavailable("web_search", why)}
    return call


class Script:
    """The Insight calls no tool (the W14 case); notes and the Writer as in the other checks. Records prompts."""

    def __init__(self):
        self.insight_first, self.writer_prompts = None, []

    def __call__(self, role, msgs, tools, schema) -> Any:
        if schema is None:
            if self.insight_first is None:
                self.insight_first = " ".join(str(x.content) for x in msgs)
            return AIMessage(content="Findings ready.")
        k, cats = EV["kpi.weekly"]["rows"][0], EV["kpi.category"]["rows"]
        if schema is m.InsightNotes:
            return m.InsightNotes(summary=[m.Cited(text="Billed this week", evidence_ids=["kpi.weekly"])] * 5,
                                  drivers=[m.Driver(vessel_category=c["vessel_category"], direction="up",
                                                    flagged_by_audit=False, explanation="largest change",
                                                    evidence_ids=["kpi.category"]) for c in cats[:3]],
                                  caveats=[])
        self.writer_prompts.append(" ".join(str(x.content) for x in msgs))
        assert k
        if schema is m.SlidesDraft:      # a revise re-drafts its related slides only (ADR-050 amendment 5, 2026-11-16)
            return wp.slides_of(sample.slot_draft(W, EV), msgs)
        assert schema is m.DeckDraft, schema
        return m.DeckDraft.model_validate(sample.slot_draft(W, EV))


def run(fetch):
    sc = Script()
    g = wp.build_graph(roles.FakeRoles(sc), InMemorySaver(), REPORTS, context_fetch=fetch)
    cfg: Any = {"configurable": {"thread_id": f"weekly_pack:live:2025-W{W:02d}:{id(sc) % 10000}"}}
    for _ in g.stream({"report_week": W}, cfg, context=context.RunContext(user), stream_mode="updates"):
        pass
    return g, cfg, sc


# %% Phase 1 — the fetch, run by code
fetch = Fetch()
g, cfg, sc = run(fetch)
st = g.get_state(cfg).values
ins = sc.insight_first or ""
p1 = {"status": st["status"], "ok": {k: st["evidence"][k]["status"] for k in ("context.suez", "context.news")},
      "in_insight": "[context.suez]" in ins and "[context.news]" in ins and "web_content" in ins,
      "no_refetch_line": "do not fetch the same window again" in ins,
      "in_writer": all("[context.suez]" in p and "[context.news]" in p for p in sc.writer_prompts),
      "calls_before_revise": fetch.calls}
for _ in g.stream(Command(resume={"decision": "revise", "approver_employee_id": FIN_MGR,
                                  "steer": "collections by customer"}), cfg, context=context.RunContext(user),
                  stream_mode="updates"):
    pass
p1["after_revise"] = (g.get_state(cfg).values["status"], fetch.calls)
assert p1 == {"status": "awaiting_approval", "ok": {"context.suez": "ok", "context.news": "ok"}, "in_insight": True,
              "no_refetch_line": True, "in_writer": True, "calls_before_revise": 1,
              "after_revise": ("awaiting_approval", 1)}, p1
print("✅ Phase 1 validation passed: the context fetched by code with an Insight that called no tool; in the Insight's "
      "and the Writer's input (news labelled web_content); one fetch per pack, none on a revise")
DONE.append(1)

# %% Phase 2 — an outage
down = Fetch(fail=True)
g, cfg, sc = run(failing_fetch(down))
st = g.get_state(cfg).values
notes = {k: st["evidence"][k]["note"] for k in ("context.suez", "context.news")}
for _ in g.stream(Command(resume={"decision": "approve", "approver_employee_id": FIN_MGR}), cfg,
                  context=context.RunContext(user), stream_mode="updates"):
    pass
pub = g.get_state(cfg).values
run_json = json.loads((Path(pub["published"]["folder"]) / "run.json").read_text(encoding="utf-8"))
real_default = wp.build_graph(None).get_graph().nodes["external_context"] is not None
p2 = {"waiting_before": st["status"], "notes": set(notes.values()), "published": pub["status"],
      "run_json": run_json["external_context"], "db_rows": pub["published"]["db_rows"],
      "fake_default": wp.no_context(user, {})["context.news"]["note"] == wp.FAKE_CONTEXT_NOTE,
      "real_default_node": real_default}
why = "TimeoutError: PortWatch did not answer"
assert p2 == {"waiting_before": "awaiting_approval", "notes": {why}, "published": "published",
              "run_json": {"context.news": {"status": "context_unavailable", "note": why},
                           "context.suez": {"status": "context_unavailable", "note": why}},
              "db_rows": "skipped (not the live reports folder)", "fake_default": True,
              "real_default_node": True}, p2
print("✅ Phase 2 validation passed: an outage → context_unavailable with its reason in the state and in the published "
      "run.json, the pack not stopped; FakeRoles fetch nothing by default")
DONE.append(2)

# %% Phase 3 — evidence rules
ids_ok = all(m.Cited(text="x", evidence_ids=[e]) for e in ("context.suez", "context.news"))
allowed = {s: v2.allowed_on("context.news", s) for s in (2, 3, 9)}
assert ids_ok and allowed == {2: True, 3: False, 9: True}, allowed
# D-EC-4: code's week summary of the transits, and a slot on it renders and binds
from datetime import date  # noqa: E402

from pipelines.agents.deck import slots  # noqa: E402

days = [{"date": f"2025-05-{d:02d}", "n_total": n} for d, n in
        [(1, 40), (2, 41), (3, 39), (4, 40), (5, 38), (6, 42), (7, 40), (8, 30), (9, 33), (10, 45), (11, 36), (12, 35),
         (13, 34), (14, 31)]]
tw = wp.transit_week(days, date(2025, 5, 8), date(2025, 5, 14))
assert tw == {"week_mean_transits": 34.9, "week_min_transits": 30, "week_min_date": "2025-05-08",
              "week_max_transits": 45, "week_max_date": "2025-05-10", "prev4_mean_transits": 40.0}, tw
ev_s = {"context.suez": {"tool": "suez_transits", "status": "ok", "rows": days, **tw}}
text, bound = slots.render_text("Transits averaged {context.suez:week_mean_transits} a day, between "
                                "{context.suez:week_min_transits} and {context.suez:week_max_transits}", ev_s)[:2]
assert text == "Transits averaged 34.9 a day, between 30 and 45" and len(bound) == 3, text
assert "week_mean_transits=34.9" in wp.digest(ev_s, ["context.suez"]), "the summary line in the digest"
print("✅ Phase 3 validation passed: context.* ids pass the evidence-id rule; slides 2 and 9 may cite them, slide 3 not")
DONE.append(3)

# %% Final Checkpoint
assert DONE == [1, 2, 3], DONE
print("✅ Final Checkpoint: Phases 1–3 passed (no LLM call, no network)")
