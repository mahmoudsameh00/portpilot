"""Database-free executor regressions (stabilization R1/R2).

Reads application code only; writes no data. Safe to rerun. Uses Events to control worker completion,
and invokes the real timeout path directly instead of relying on sub-second timer races.
"""
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists())
sys.path.insert(0, str(ROOT))

from pipelines.api import runs, schemas
from pipelines.api.errors import ApiError
from pipelines.api.routers.packs import _result


def settled(runner, run):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with runner._lock:
            if run.id not in runner._occupied:
                return
        time.sleep(0.005)
    raise AssertionError("worker did not settle")


def failed_call(call, status):
    try:
        call()
    except ApiError as exc:
        assert exc.status == status, exc
    else:
        raise AssertionError(f"expected {status}")


# %% Phase 1 — result validation and durable end ordering
def results():
    runner = runs.Runner(slots=1, queue=2)
    recorded = []
    try:
        with patch.object(runs, "failure", return_value=(500, "internal_error", "invalid worker result")):
            bad = runner.submit(1, "check", lambda r: {"status": "invalid", "problems": [{}]},
                                on_finish=lambda state, result: recorded.append((state, result)))
            settled(runner, bad)
        assert bad.state == "failed" and bad.error["status"] == 500
        assert recorded == [("failed", None)]
        assert [e.event for e in bad.events].count("failed") == 1
        problem = {"rule": "V10", "message": "unsupported causal claim", "slide": 9}
        result = _result("pack:1", "awaiting_approval", None, [problem], 0)
        assert schemas.AnswerData.model_validate(result).problems == ["V10: unsupported causal claim"]

        def record(state, result):
            assert state == "done" and result["problems"] == []
            recorded.append((state, result))

        good = runner.submit(1, "check", lambda r: {"status": "ok"}, on_finish=record)
        settled(runner, good)
        assert good.state == "done" and len(recorded) == 2
        assert [e.event for e in good.events][-2:] == ["answer", "done"]

        def broken_record(state, result):
            raise RuntimeError("simulated persistence failure")

        with patch.object(runs.log, "exception"):
            broken = runner.submit(1, "check", lambda r: {"status": "ok"}, on_finish=broken_record)
            settled(runner, broken)
        assert broken.state == "failed" and broken.error["status"] == 500
        assert not any(e.event == "answer" for e in broken.events)
    finally:
        runner.shutdown()
    print("✅ Phase 1 validation passed. 4 result/record cases.")


# %% Phase 2 — actual worker capacity, expired queue, ownership, shutdown
def capacity():
    runner = runs.Runner(slots=1, queue=1)
    entered, release = threading.Event(), threading.Event()
    called, recorded = [], []

    def blocked(run):
        entered.set()
        assert release.wait(5)
        failed_call(run.check_active, 504)
        return {"status": "late"}

    try:
        first = runner.submit(1, "check", blocked, conversation_id="one")
        assert entered.wait(5)
        queued = runner.submit(1, "check", lambda r: called.append(r.id) or {"status": "ok"},
                               on_finish=lambda state, result: recorded.append(state))
        runner._timeout(first)
        failed_call(lambda: runner.submit(1, "check", lambda r: {"status": "ok"}), 429)
        runner._timeout(queued)
        settled(runner, queued)
        assert recorded == ["failed"] and not called
        assert queued.state == "failed" and not any(e.event == "started" for e in queued.events)
        failed_call(lambda: runner.submit(1, "check", lambda r: {"status": "ok"}, conversation_id="one"), 409)
        replacement = runner.submit(1, "check", lambda r: {"status": "ok"})
        failed_call(lambda: runner.submit(1, "check", lambda r: {"status": "ok"}), 429)
        runner.shutdown()
        settled(runner, replacement)
        assert replacement.state == "failed" and replacement.error["status"] == 503
        release.set()
        settled(runner, first)
        assert first.state == "failed" and len([e for e in first.events if e.event == "failed"]) == 1
        assert not any(e.event == "answer" for e in first.events)
        assert not runner._busy_conversations
        failed_call(lambda: runner.submit(1, "check", lambda r: {"status": "ok"}), 503)
        tid = runner.reserve_thread(lambda: "test:1")
        failed_call(lambda: runner.submit(1, "check", lambda r: {"status": "ok"}, thread_id=tid), 503)
        assert tid not in runner._reserved_threads
    finally:
        release.set()
        runner.shutdown()
    print("✅ Phase 2 validation passed. Timeout capacity, queued cancellation, conversation ownership, shutdown.")


# %% Phase 3 — simultaneous admissions cannot overfill the executor
def admission():
    runner = runs.Runner(slots=1, queue=1)
    gate, release = threading.Barrier(8), threading.Event()
    accepted, refused = [], []

    def work(run):
        assert release.wait(5)
        return {"status": "ok"}

    def submit():
        gate.wait(timeout=5)
        try:
            accepted.append(runner.submit(1, "check", work))
        except ApiError as exc:
            refused.append(exc.status)

    threads = [threading.Thread(target=submit) for _ in range(8)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
            assert not thread.is_alive()
        assert len(accepted) == 2 and refused == [429] * 6
        release.set()
        for run in accepted:
            settled(runner, run)
            assert run.state == "done"
    finally:
        release.set()
        runner.shutdown()
    print("✅ Phase 3 validation passed. 8 concurrent admissions: 2 accepted, 6 refused.")


def main():
    results()
    capacity()
    admission()
    print("✅ Final Checkpoint: lifecycle checks passed; no databases, models or artifact writes.")


if __name__ == "__main__":
    main()
