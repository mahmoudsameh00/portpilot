"""Approval safety regressions, no database or model calls.

Reads code only; writes no artifacts. Stub connections exercise the shared lock protocol; real PostgreSQL
contention remains an owner-run integration check. Safe to rerun through tools/run.py.
"""
import copy
import sys
from contextlib import nullcontext
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists())
sys.path.insert(0, str(ROOT))

from pydantic import ValidationError
from pipelines.agents import approver_request as ar, locks, scheduling
from pipelines.agents.graphs import weekly_pack as wp
from pipelines.api import runs
from pipelines.api.errors import ApiError
from pipelines.api.routers import packs
from pipelines.api.routers.ask import RunEvents


def conflict(call):
    try:
        call()
    except ApiError as exc:
        assert exc.status == 409
    else:
        raise AssertionError("a stale/busy decision was accepted")


# %% Phase 1 — same lock across API and CLI, with release on exceptions
def lock_protocol():
    held, calls = set(), []

    class Connection:
        def execute(self, sql, args):
            calls.append((sql, args))
            key = args[0]
            if "try" in sql:
                acquired = key not in held
                if acquired:
                    held.add(key)
                return SimpleNamespace(fetchone=lambda: (acquired,))
            held.remove(key)
            return SimpleNamespace(fetchone=lambda: (True,))

    with patch.object(locks.checkpointer, "conninfo", return_value="stub") as info, \
            patch.object(locks.psycopg, "connect", side_effect=lambda *a, **k: nullcontext(Connection())):
        with locks.thread_lock("pack:1"):
            conflict(lambda: runs.thread_lock("pack:1").__enter__())
            with runs.thread_lock("pack:2"):
                assert len(held) == 2
        try:
            with runs.thread_lock("pack:1"):
                raise ValueError("work failed")
        except ValueError:
            pass
        assert not held
        assert info.call_args.args == ("PG_AGENT_USER", "PG_AGENT_PASSWORD")
    assert len(calls) == 7
    print("✅ Phase 1 validation passed. Shared lock contention, independent threads, exception release.")


# %% Phase 2 — all review inputs invalidate old decisions, including after admission
def reviews():
    state = {"draft": {"title": "pack"}, "charts": {}, "evidence": {}, "insight": {}, "approval_log": []}
    sha = ar.draft_sha(state)
    for key in ("draft", "charts", "evidence", "insight", "approval_log", "revision", "status", "verdict", "readiness"):
        changed = {**state, key: {"changed": True}}
        assert ar.draft_sha(changed) != sha, key
    assert ar.draft_sha({**state, "llm_usage": [1]}) == sha
    try:
        packs.DirectDecisionIn(decision="approve")
    except ValidationError:
        pass
    else:
        raise AssertionError("an unversioned decision was accepted")
    body = packs.DirectDecisionIn(decision="approve", draft_sha=sha)
    assert body.changes() == {}
    snap = SimpleNamespace(values=copy.deepcopy(state), interrupts=[1])
    graph = SimpleNamespace(get_state=lambda cfg: snap, stream=Mock())
    cfg = {"configurable": {"thread_id": "pack:1"}}
    packs.require_review(graph, cfg, sha)
    request = SimpleNamespace(state=SimpleNamespace(request_id="check"), app=SimpleNamespace(
        state=SimpleNamespace(runner=SimpleNamespace(submit=lambda owner, kind, work, **kw: work))))
    with patch.object(packs, "_decidable", return_value=(graph, cfg, 1, state)), \
            patch.object(packs, "_accepted", side_effect=lambda req, work, tid: work):
        work = packs.decide("pack:1", body, SimpleNamespace(employee_id=1), request)
    # Another approver edits charts between the HTTP acceptance and execution.
    snap.values["charts"] = {"trend": {"weeks": 4}}
    with patch.object(packs.context, "load_user", return_value=SimpleNamespace(employee_id=1)), \
            patch.object(runs, "thread_lock", return_value=nullcontext()), \
            patch.object(packs.tracing, "trace", return_value=nullcontext()):
        conflict(lambda: work(runs.Run("run:1", 1, "pack_decision", "pack:1")))
    graph.stream.assert_not_called()
    snap.values = state
    snap.interrupts = []
    conflict(lambda: packs.require_review(graph, cfg, sha))
    print("✅ Phase 2 validation passed. 9 review inputs, required version, queued stale decision, ended pack.")


# %% Phase 3 — expired approvals cannot enter approval or publication
def deadlines():
    def expired():
        raise TimeoutError("expired")
    ctx = SimpleNamespace(check_active=expired)
    for call in (lambda: wp.approval({}, {}, Path("unused"), ctx),
                 lambda: wp.make_publisher(Path("unused"))({}, {}, SimpleNamespace(context=ctx))):
        try:
            call()
        except TimeoutError:
            pass
        else:
            raise AssertionError("expired mutation was allowed")
    run = runs.Run("expired", 1, "ask", "ask:1")
    run.claim()
    callbacks = RunEvents(run, {"finance_kpi"})
    assert callbacks.raise_error
    for call in (lambda: callbacks.on_chain_start(None, {}, run_id="node"),
                 lambda: callbacks.on_tool_start({"name": "finance_kpi"}, "", run_id="tool")):
        try:
            call()
        except ApiError as exc:
            assert exc.status == 504
        else:
            raise AssertionError("an expired graph started more work")
    print("✅ Phase 3 validation passed. Approval, publication, node and tool expiry guards.")


# %% Phase 4 — scheduler and retention recheck state inside the mutation lock
def schedules():
    now = scheduling.now_utc()
    tid = f"{scheduling.LIVE_PREFIX}01:1"
    pending = scheduling.ThreadInfo(tid, 1, 1, "pending", "awaiting_approval", now, 1)
    graph = SimpleNamespace(stream=Mock())
    with patch.object(scheduling, "describe_all", side_effect=[[], [pending]]), \
            patch.object(locks, "thread_lock", return_value=nullcontext()):
        result = scheduling.fire(graph, None, None, SimpleNamespace(employee_id=1), Path("unused"), notify=False)
    assert "skipped" in result
    graph.stream.assert_not_called()
    old = scheduling.ThreadInfo(tid, 1, 1, "ended", "published", now - timedelta(days=31), 1)
    snap = SimpleNamespace(next=(), interrupts=(), created_at=now.isoformat())
    graph = SimpleNamespace(get_state=lambda cfg: snap)
    saver = SimpleNamespace(delete_thread=Mock())
    with patch.object(locks, "thread_lock", return_value=nullcontext()), \
            patch.object(scheduling, "append_jsonl") as archive:
        result = scheduling.prune(graph, saver, [old], Path("unused"), now=now)
        assert result["kept"] == 1 and not result["deleted"]
        archive.assert_not_called()
        saver.delete_thread.assert_not_called()
    print("✅ Phase 4 validation passed. Changed schedule and refreshed retention candidate are preserved.")


if __name__ == "__main__":
    lock_protocol()
    reviews()
    deadlines()
    schedules()
    print("✅ Final Checkpoint: approval safety checks passed; no database, model or artifact writes.")
