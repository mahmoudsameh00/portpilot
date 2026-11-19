"""Shared traffic-claim regressions (R5/R6). Reads fixed EN/AR cases and code; no DB/model/network/artifact writes.
Safe to rerun with dev/tools/run.py. Does not change M17 or the frozen real-model golden sets.
"""
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists())
sys.path.insert(0, str(ROOT))

from pipelines.agents import traffic_claims as policy
from pipelines.agents.deck import validator
from pipelines.agents.graphs import finance_qa, supervisor
from pipelines.agents.graphs import models, weekly_pack

CASES = Path(__file__).with_name("fixtures") / "traffic_claims.json"
FIXTURE_SHA256 = "6c9364a53abc44988defef15a469f88c9e28f55a231f83f74d0770c39fc2e53f"


# the sentences the real models wrote in the Phase 6 acceptance run (tl1, 2026-11-12), labels reviewed by hand
REAL_CASES = Path(__file__).with_name("fixtures") / "traffic_claims_real.json"
REAL_SHA256 = "2e9c6786112e67ea935c7477f8d222638915a33b0e2352ebf5e76818e18fc3df"


def evidence(verdict, eid="context.link", source="finance.kpi_traffic_link", week=30):
    return {eid: {"tool": "finance_kpi", "status": "ok", "source": {"kind": "view", "name": source,
                 "filter": f"report_week = {week}"}, "rows": [{"report_week": week, "link": verdict}]}}


# %% Phase 1 — frozen adversarial sentences through the policy
def sentences():
    assert hashlib.sha256(CASES.read_bytes()).hexdigest() == FIXTURE_SHA256, "review fixture changes explicitly"
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    failed = []
    for case in cases:
        problems = policy.problems(case["text"], ["context.link"], evidence(case["verdict"]))
        if bool(problems) != case["reject"]:
            failed.append((case, problems))
    assert not failed, failed
    assert len(cases) == 66
    for lang in ("en", "ar"):
        for verdict in ("link", "no_link", None):
            assert not policy.problems(policy.wording(verdict, lang), ["context.link"], evidence(verdict))
    print("✅ Phase 1 validation passed. 66 EN/AR cases and 6 fixed statements.")


# %% Phase 2 — provenance, citation and verdict ambiguity
def provenance():
    text = "Billing moved with Suez transits so far this year"
    for source in policy.VIEWS:
        ev = evidence("link", "insight.call_9", source)
        assert not policy.problems(text, ["insight.call_9"], ev)
    ev = evidence("link", "insight.call_9")
    assert policy.problems(text, [], ev)
    assert policy.problems(text, ["context.link"], ev)
    ev = evidence("link")
    for key, value in (("tool", "search_documents"), ("status", "not_permitted"),
                       ("source", {"kind": "view", "name": "finance.kpi_weekly"})):
        assert policy.problems(text, ["context.link"], {"context.link": {**ev["context.link"], key: value}})
    ev = {**evidence("link", "insight.a"), **evidence("no_link", "insight.b")}
    assert policy.problems(text, list(ev), ev)
    assert policy.problems(text, ["context.link"], evidence(None))
    assert policy.problems(text, [], {})
    print("✅ Phase 2 validation passed. Dynamic IDs, 3 view provenances, missing/refused/uncited/ambiguous results.")


# %% Phase 3 — all answer surfaces enforce the same rule
def surfaces():
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    for case in cases:
        ev = evidence(case["verdict"], "insight.call_9")
        used = list(ev)
        answer = {"status": "answered", "answer": case["text"], "evidence_ids": used}
        expected = case["reject"]
        assert bool(validator.link_problems(case["text"], used, ev)) == expected, case
        for check in (finance_qa.check_answer, supervisor.check_supervisor_answer):
            _, _, problems = check(answer, ev, case["text"], "ar" if "الفواتير" in case["text"] else "en")
            assert any(p.startswith("V10") for p in problems) == expected, (case, problems)
        notes = {"summary": [{"text": case["text"], "evidence_ids": used}]}
        assert bool(policy.note_problems(notes, ev)) == expected
    print("✅ Phase 3 validation passed. 66 cases each: deck, finance Q&A, supervisor Q&A, notes.")


# %% Phase 4 — implicit financial context and unsafe model notes stop before the Writer
def integration():
    ev = evidence("no_link")
    for question, text in (("Why did billing fall?", "Because Suez traffic fell."),
                           ("ليه الفواتير قلت؟", "بسبب انخفاض عبور قناة السويس.")):
        answer = {"status": "answered", "answer": text, "evidence_ids": list(ev)}
        for check in (finance_qa.check_answer, supervisor.check_supervisor_answer):
            assert any(p.startswith("V10") for p in check(answer, ev, question)[2])
    ev["kpi.weekly"] = {"tool": "finance_kpi", "status": "ok", "rows": [{"billed_sdr": 100}]}
    assert policy.problems("Because Suez traffic fell, {kpi.weekly:billed_sdr|M}.", list(ev), ev)
    reply = SimpleNamespace(parsed=models.InsightNotes(summary=[models.Cited(
        text="Billing fell because Suez traffic fell", evidence_ids=["context.link"])]), calls=[])
    roles = SimpleNamespace(get=lambda role: SimpleNamespace(structured=lambda msgs, schema: reply))
    node = weekly_pack.make_insight_notes(roles)
    # no single measured verdict in the run (two results that disagree): nothing to repair with → the run stops
    state = {"evidence": {**evidence("link", "insight.a"), **evidence("no_link", "insight.b")}, "messages": [],
             "report_week": 30}
    result = node(state)
    assert result["status"] == "output_invalid" and "V10" in result["stop_reason"]
    assert "insight" not in result and "normalized" not in result
    assert weekly_pack.after_agent_step("writer")(result) == "__end__"
    assert weekly_pack.after_agent_step("writer")({**result, "before_revise": {"draft": {}}}) == "revise_failed"
    # the run's own verdict is measured: the unsafe sentence is replaced by the fixed wording, the run goes on (D-TL-11)
    state = {"evidence": evidence("no_link"), "messages": [], "report_week": 30}
    result = node(state)
    assert "status" not in result and result["insight"]["summary"][0]["text"] == policy.wording("no_link"), result
    assert len(result["normalized"]) == 1 and result["normalized"][0].startswith("insight_notes V10: summary[0]")
    assert weekly_pack.after_agent_step("writer")(result) == "writer"
    reply.parsed = models.InsightNotes(summary=[models.Cited(text=policy.wording("no_link"),
                                                           evidence_ids=["context.link"])])
    clean = node(state)
    assert clean["insight"]["summary"][0]["text"] == policy.wording("no_link") and "normalized" not in clean
    print("✅ Phase 4 validation passed. EN/AR short answers, implicit slot, unrepairable notes stop/restore, "
          "repairable notes go on with the fixed wording, clean notes pass untouched.")


# %% Phase 5 — the real models' sentences (Phase 6 run tl1) and the notes repair
def real_sentences():
    assert hashlib.sha256(REAL_CASES.read_bytes()).hexdigest() == REAL_SHA256, "review fixture changes explicitly"
    cases = json.loads(REAL_CASES.read_text(encoding="utf-8"))
    failed = [(c, p) for c in cases
              if bool(p := policy.problems(c["text"], ["context.link"], evidence(c["verdict"], week=c["week"])))
              != c["reject"]]
    assert not failed, failed
    assert len(cases) == 53 and sum(c["reject"] for c in cases) == 3
    # repair: the sound parts stay, the refused part goes, the fixed wording and the M17 id are added
    ev = {**evidence(None, week=10), "context.suez": {"tool": "suez_transits", "status": "ok"}}
    notes = {"summary": [{"text": "Audit flagged 2 of 19 invoices; billing moved with Suez transits this year.",
                          "evidence_ids": ["audit.week"]}],
             "context": [{"text": "Suez transits averaged 40.1/day this week (min 35; max 47); the traffic link test "
                                  "shows no measurable link between weekly invoice count and Suez transits.",
                          "evidence_ids": ["context.suez", "context.link"]}],
             "caveats": ["Traffic link is no_link; billing is not claimed to move with Suez transits.",
                         "Week 10 is a warm-up week."]}
    assert len(policy.note_problems(notes, ev)) == 3
    fixed, done = policy.repair_notes(notes, ev)
    too_few = policy.wording(None)
    assert not policy.note_problems(fixed, ev) and len(done) == 3, (fixed, done)
    assert fixed["summary"][0] == {"text": f"Audit flagged 2 of 19 invoices. {too_few}",
                                   "evidence_ids": ["audit.week", "context.link"]}
    assert fixed["context"][0]["text"] == f"Suez transits averaged 40.1/day this week (min 35; max 47). {too_few}"
    assert fixed["caveats"] == [too_few, "Week 10 is a warm-up week."]
    assert notes["caveats"][0].startswith("Traffic link") and notes["summary"][0]["evidence_ids"] == ["audit.week"]
    arabic = {"summary": [{"text": "الفواتير قلّت بسبب انخفاض حركة قناة السويس", "evidence_ids": ["context.link"]}]}
    assert policy.repair_notes(arabic, evidence("no_link"))[0]["summary"][0]["text"] == policy.wording("no_link", "ar")
    # every pinned unsafe sentence (the 66 pinned + the real ones) ends as safe notes, or is left for the stop
    for c in [*json.loads(CASES.read_text(encoding="utf-8")), *cases]:
        ev = evidence(c["verdict"], week=c.get("week", 30))
        out, done = policy.repair_notes({"summary": [{"text": c["text"], "evidence_ids": ["context.link"]}]}, ev)
        assert not policy.note_problems(out, ev) and bool(done) == c["reject"], (c, out)
    print("✅ Phase 5 validation passed. 53 real-model sentences (50 sound pass, 3 unsafe refused); repair keeps the "
          "sound parts, adds the fixed wording + the M17 id, EN/AR; all 119 pinned cases end safe.")


if __name__ == "__main__":
    sentences()
    provenance()
    surfaces()
    integration()
    real_sentences()
    print(f"Fixture SHA-256: {hashlib.sha256(CASES.read_bytes()).hexdigest()}")
    print("✅ Final Checkpoint: shared traffic-claim policy passed; no database or model calls.")
