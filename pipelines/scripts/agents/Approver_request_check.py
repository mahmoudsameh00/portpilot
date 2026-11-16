"""Approver request check (approver-request plan §3, Phase A): the manager's request in words → the pack's own decisions.

Plan:    docs/archive/2026-11-07_Approver_request_plan.md (APPROVED 2026-11-07, owner R2 / R3).
Run:     uv run python tools/run.py pipelines/scripts/agents/Approver_request_check.py  (from the project root)

Reads:   PostgreSQL read-only (PG_RO_USER): employees, the finance and audit views of one week.
         No LLM call: the Insight, the Writer and the request interpreter are scripted fake models (FakeRoles).
Writes:  a throw-away temp folder for previews / the published pack (the real `reports/` is never touched);
         checkpoints in memory (InMemorySaver).
Re-run:  safe (read-only on the database).

Phases
1. Proposal (no graph run): each request kind → its steps; a mixed request → revise then edit (R3); an unplaceable
   request → ask-back; a change the pack would refuse (a 5-week trend, a revise with text edits) → ask-back from code
   before any run; an invalid reply twice → the fixed ask-back in the request's language.
2. Apply on a waiting pack: a chart, an addition + an edit, a steer, a mixed request (one wait at the end, the text
   read again on the new draft), a stale proposal, an edit with an unbound number (the Validator holds the pack),
   approve → published.
Final Checkpoint.
"""
# %% Setup
import sys
import tempfile
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from pipelines.agents import approver_request as ar  # noqa: E402
from pipelines.agents import roles  # noqa: E402
from pipelines.agents.deck import sample  # noqa: E402
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


def _q(v, d):
    return Decimal(str(v)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)


def m_sdr(v, signed=False):
    q = _q(Decimal(str(v)) / 10 ** 6, 2)
    return (("+" if q > 0 else "") if signed else "") + f"{q:.2f}".replace("-", "−") + " M SDR"


class Script:
    """The Insight (no tool round), the Writer (deck/sample.py's slot draft) and the interpreter (a queue of replies:
    a dict, or a callable on the messages). `text_only_seen` records the D-AR-1 second reading."""

    def __init__(self, ev):
        self.ev, self.queue, self.text_only_seen, self.insight_calls = ev, [], 0, 0

    def __call__(self, role, msgs, tools, schema) -> Any:      # FakeRole also takes a dict to validate
        if schema is ar.ApproverRequest:
            text = " ".join(str(x.content) for x in msgs)
            self.text_only_seen += "already applied" in text
            nxt = self.queue.pop(0)
            return nxt(text) if callable(nxt) else nxt
        if schema is None:
            self.insight_calls += 1
            return AIMessage(content="Findings ready.")
        k, cats, aud = self.ev["kpi.weekly"]["rows"][0], self.ev["kpi.category"]["rows"], self.ev["audit.week"]
        if schema is m.InsightNotes:
            summary = [m.Cited(text=f"Billed {m_sdr(k['billed_sdr'])} in week {W} of 2025", evidence_ids=["kpi.weekly"]),
                       m.Cited(text=f"Budget variance {m_sdr(k['budget_variance_sdr'], True)}",
                               evidence_ids=["kpi.weekly"]),
                       m.Cited(text="Top drivers: " + ", ".join(c["vessel_category"] for c in cats[:3]),
                               evidence_ids=["kpi.category"]),
                       m.Cited(text=f"AR {m_sdr(k['ar_sdr'])}", evidence_ids=["kpi.weekly"]),
                       m.Cited(text=f"{aud['invoices_checked']} invoices checked", evidence_ids=["audit.week"])]
            drivers = [m.Driver(vessel_category=c["vessel_category"], direction="up", flagged_by_audit=False,
                                explanation="largest change", evidence_ids=["kpi.category"]) for c in cats[:3]]
            return m.InsightNotes(summary=summary, drivers=drivers, caveats=[])
        if schema is m.SlidesDraft:                      # a revise re-drafts its related slides only
            return wp.slides_of(sample.slot_draft(W, self.ev), msgs)
        assert schema is m.DeckDraft, schema
        return m.DeckDraft.model_validate(sample.slot_draft(W, self.ev))


EV = {**wp.kpi_evidence(user, W), **wp.audit_evidence(user, W, "live")}
REPORTS = Path(tempfile.mkdtemp(prefix="approver_request_check_"))
_n = iter(range(1, 1000))


def new_pack():
    """A fresh pack of week W waiting for its approval: (graph, config, script)."""
    sc = Script(EV)
    g = wp.build_graph(roles.FakeRoles(sc), InMemorySaver(), REPORTS)
    cfg: Any = {"configurable": {"thread_id": f"weekly_pack:live:2025-W{W:02d}:{next(_n)}"}}
    for _ in g.stream({"report_week": W}, cfg, context=context.RunContext(user), stream_mode="updates"):
        pass
    return g, cfg, sc


def req(**kw):
    return {"understood": kw.pop("understood", "ok"), **kw}


g0, cfg0, sc0 = new_pack()
ok0, st0 = ar.waiting(g0, cfg0)
assert ok0 and st0["verdict"]["passed"], st0.get("verdict")
SLIDE6 = next(i for i, b in enumerate(st0["draft"]["bullets"]) if b["slide"] == 6)

# %% Phase 1 — Proposal: the request → its steps, before anything runs (R2)
# The interpreter's reply is one of the pack's own kinds; code orders them (a revise first, R3) and checks every
# step with `ApprovalDecision` (D1, the caps) so a change the pack would refuse is asked back before any run.
cases = {
    "chart": (req(action="change", charts=[{"chart": "trend", "series": ["billed_sdr", "collected_sdr"], "weeks": 8}]),
              [{"decision": "edit", "edits": [], "additions": [],
                "charts": [{"chart": "trend", "series": ["billed_sdr", "collected_sdr"], "weeks": 8}]}], False),
    "steer": (req(action="change", steer="collections by customer"),
              [{"decision": "revise", "analysis_edits": [], "charts": [], "steer": "collections by customer"}], False),
    "mixed": (req(action="change", steer="collections by customer",
                  additions=[{"slide": 4, "text": "Finance will follow up with the commercial team."}],
                  edits=[{"bullet": SLIDE6, "text": "Receivables need attention this week."}]),
              [{"decision": "revise", "analysis_edits": [], "charts": [], "steer": "collections by customer"},
               {"decision": "edit", "additions": [{"slide": 4, "text": "Finance will follow up with the commercial "
                                                                       "team."}]}], True),
    "approve": (req(action="approve"), [{"decision": "approve"}], False),
}
got = {}
for name, (reply, steps, reread) in cases.items():
    sc0.queue = [reply]
    p = ar.propose(f"request {name}", st0, roles.FakeRoles(sc0))
    got[name] = (p.steps == steps, p.reread_text == reread, p.ask_back, p.model_calls)
sc0.queue = [req(action="ask_back", ask_back="Which chart do you mean?")]
asked = ar.propose("change the chart", st0, roles.FakeRoles(sc0))
sc0.queue = [req(action="change", charts=[{"chart": "trend", "weeks": 5}])]
bad_weeks = ar.propose("show five weeks", st0, roles.FakeRoles(sc0))
sc0.queue = [req(action="change", charts=[{"chart": "trend", "weeks": 26}])]
window = ar.propose("show half a year", st0, roles.FakeRoles(sc0))      # week 23 < 26: the catalogue's week rule
sc0.queue = [req(action="approve")]
no_word = ar.propose("بص تاني على المتأخرات", st0, roles.FakeRoles(sc0))  # D-AR-8: "approve" with no word for it
sc0.queue = [{"action": "maybe"}, {"action": "maybe"}]
invalid_ar = ar.propose("غيّر الرسمة", st0, roles.FakeRoles(sc0))
shape_refused = []
for bad in (req(action="change"), req(action="ask_back")):
    try:
        ar.ApproverRequest.model_validate(bad)
    except Exception:  # noqa: BLE001 — a pydantic ValidationError
        shape_refused.append(bad["action"])

actual = {"cases": got, "ask_back": (asked.steps, asked.ask_back), "bad_weeks": (bad_weeks.steps,
                                                                                 bool(bad_weeks.ask_back)),
          "window": (window.steps, "week 26 or later" in (window.ask_back or "")),
          "no_word": (no_word.steps, no_word.ask_back),
          "invalid_ar": (invalid_ar.steps, invalid_ar.ask_back), "shape_refused": shape_refused,
          # D-AR-11: an approve that carries changes is read as a change (the changes are what was asked)
          "approve_with_steer": ar.ApproverRequest.model_validate(req(action="approve", steer="x")).action,
          "view_has_indexes": f"[{SLIDE6}] slide 6" in ar.view_of(st0) and "summary[0]" in ar.view_of(st0)}
expected = {"cases": {k: (True, True, None, 1) for k in cases},
            "ask_back": ([], "Which chart do you mean?"), "bad_weeks": ([], True), "window": ([], True),
            "no_word": ([], ar.ASK_DECIDE["approve"]["ar"]),
            "invalid_ar": ([], ar.ASK_UNCLEAR["ar"]), "shape_refused": ["change", "ask_back"], "approve_with_steer": "change",
            "view_has_indexes": True}
assert actual == expected, actual
print(f"Phase 1: {len(cases)} kinds → steps, ask-backs 3, shapes refused {len(shape_refused)}")
print("✅ Phase 1 validation passed: each kind → its steps, a mixed request → revise then edit with the text read "
      "again, ask-back on an unplaceable request, a refused change asked back before any run, the fixed Arabic "
      "ask-back after two invalid replies")
DONE.append(1)

# %% Phase 2 — Apply on a waiting pack
# Each step is a resume of the waiting pack; the graph checks and the Validator binds as for any decision. A mixed
# request runs as one revise then one edit on the new draft (the text read again: D-AR-1), one wait at the end. A
# proposal read on another draft is refused (stale). An edit with a number the evidence does not hold leaves the pack
# waiting with the Validator's problem (approve is then not offered). Approve publishes.
res = {}


def run_case(reply, request, reread_reply=None):
    g, cfg, sc = new_pack()
    _, st = ar.waiting(g, cfg)
    sc.queue = [reply] + ([reread_reply] if reread_reply else [])
    p = ar.propose(request, st, roles.FakeRoles(sc))
    out = ar.apply(g, cfg, context.RunContext(user), p, request, FIN_MGR, roles.FakeRoles(sc))
    return out, ar.waiting(g, cfg), sc


out, (wait, st), _ = run_case(cases["chart"][0], "show billed and collected over 8 weeks")
res["chart"] = (out["status"], [o["outcome"] for o in out["outcomes"]], wait,
                st["charts"].get("trend", {}).get("weeks"), st["verdict"]["passed"])

out, (wait, st), _ = run_case(req(action="change", edits=[{"bullet": SLIDE6, "text": "Receivables need attention "
                                                                                     "this week."}],
                                  additions=[{"slide": 4, "text": "Finance will follow up with the commercial team."}]),
                              "reword slide 6 and add a follow-up on slide 4")
res["edit_add"] = (out["status"], [o["outcome"] for o in out["outcomes"]], wait,
                   sum(b.get("origin") == "approver" for b in st["draft"]["bullets"]), st["verdict"]["passed"])

out, (wait, st), sc = run_case(cases["steer"][0], "look again at collections by customer")
res["steer"] = (out["status"], [o["outcome"] for o in out["outcomes"]], wait, sc.insight_calls, st["redrafted"])


def reread(text):                 # D-AR-1: the second reading names a bullet of the NEW draft
    assert "already applied" in text
    idx = text.split("] slide 6 (")[0].rsplit("[", 1)[1]
    return req(action="change", edits=[{"bullet": int(idx), "text": "Receivables need attention this week."}])


out, (wait, st), sc = run_case(cases["mixed"][0], "look again at collections, add a follow-up, reword slide 6",
                               reread_reply=reread)
res["mixed"] = (out["status"], [o["outcome"] for o in out["outcomes"]], wait, sc.text_only_seen,
                sum(b.get("origin") == "approver" for b in st["draft"]["bullets"]),
                any(b["text"] == "Receivables need attention this week." for b in st["draft"]["bullets"]),
                st["verdict"]["passed"])

g, cfg, sc = new_pack()
_, st = ar.waiting(g, cfg)
sc.queue = [cases["chart"][0]]
p = ar.propose("show 8 weeks", st, roles.FakeRoles(sc))
p.draft_sha = "0" * 16
res["stale"] = ar.apply(g, cfg, context.RunContext(user), p, "x", FIN_MGR, roles.FakeRoles(sc))["status"]

out, (wait, st), _ = run_case(req(action="change", edits=[{"bullet": SLIDE6, "text": "Receivables reached 999.99 M SDR "
                                                                                     "this week."}]),
                              "say receivables reached 999.99 M")
res["unbound"] = (out["status"], wait, st["verdict"]["passed"])

out, (wait, st), _ = run_case(cases["approve"][0], "approve it")
res["approve"] = (out["status"], [o["outcome"] for o in out["outcomes"]], st["status"],
                  (Path(st["published"]["folder"]) / "deck.pptx").exists())

expected = {"chart": ("applied", ["edited"], True, 8, True),
            "edit_add": ("applied", ["edited"], True, 1, True),
            "steer": ("applied", ["revised"], True, 2, True),
            "mixed": ("applied", ["revised", "edited"], True, 1, 1, True, True),
            "stale": "stale",
            "unbound": ("applied", True, False),
            "approve": ("applied", ["approved"], "published", True)}
assert res == expected, res
print(f"Phase 2: {len(res)} requests applied on waiting packs")
print("✅ Phase 2 validation passed: a chart, an edit + addition, a steer and a mixed request applied and waiting "
      "again (the mixed one as revise → edit on the new draft), a stale proposal refused, an unbound number held by "
      "the Validator, approve published")
DONE.append(2)

# %% Final Checkpoint
assert DONE == [1, 2], DONE
print("✅ Final Checkpoint: Phases 1–2 passed (no LLM call; the real-model evaluation is Approver_request_eval.py)")
