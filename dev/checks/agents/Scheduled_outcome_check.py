"""Stabilization R8: scheduled business outcomes reach the exit code, durable log and cron check-in.

Run: uv run python dev/tools/run.py dev/checks/agents/Scheduled_outcome_check.py
Reads: code only. Writes: temporary logs, automatically removed. No database, network or model calls.
Re-run: safe. Final Checkpoint: dev/checkpoints/agents/Scheduled_outcome_check.md.
"""
# %% Setup
import importlib.util
import io
import json
import sys
import tempfile
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists())
sys.path.insert(0, str(ROOT))
from pipelines.agents import monitoring, scheduling  # noqa: E402


def record(status, state="ended", brief=None):
    return {"decision": {"action": "start"},
            "result": {"thread_id": "check:1", "state": state, "status": status, "brief": brief}}


# %% Phase 1 — Explicit success, idle, stopped and degraded outcomes
pack_cases = [
    ("pending", record("awaiting_approval", "pending"), 0),
    ("published", record("published"), 0),
    ("pending_sync", {**record("published"), "publication_sync": "pending"}, 5),
    ("wait", {"decision": {"action": "wait"}}, 0),
    ("done", {"decision": {"action": "done"}}, 0),
    ("race", {"skipped": "schedule changed"}, 0),
    *[(s, record(s), 4) for s in ("output_invalid", "validation_failed", "not_ready", "not_permitted")],
    ("incomplete", record("running", "stalled"), 4),
    ("empty", {"decision": {"action": "start"}}, 4),
]
watch_cases = [("ok", record("ok", brief="ok"), 0), ("quiet", record("ok", brief="no_alerts"), 0),
               ("no_brief", record("ok", brief="output_invalid"), 5),
               ("bad_brief", record("ok", brief="validation_failed"), 5),
               ("stopped", record("not_ready"), 4), ("done", {"decision": {"action": "done"}}, 0)]
for product, cases in (("weekly_pack", pack_cases), ("voyage_watch", watch_cases)):
    for name, rec, code in cases:
        assert scheduling.operational_outcome(rec, product)["exit"] == code, (product, name)
assert (len(pack_cases), len(watch_cases)) == (12, 6)
print("✅ Phase 1 validation passed. 12 pack and 6 watch outcomes, including pending sync, degraded briefs and malformed results.")


# %% Phase 2 — Actual CLI entry points, durable JSONL and real cron context (recording transport)
def load_cli(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"pipelines/scripts/agents/{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tested = 0
with tempfile.TemporaryDirectory() as temp:
    for stem, cases, fire in (("Weekly_pack", pack_cases, "fire"), ("Voyage_watch", watch_cases, "fire_watch")):
        cli = load_cli(stem)
        extra = [("quota", RuntimeError("quota_exhausted"), 1), ("database", "unreachable", 2),
                 ("identity", "invalid_identity", 3)]
        for name, result, code in [*cases, *extra]:
            events = []
            with ExitStack() as stack:
                stack.enter_context(patch.object(cli, "LOG", Path(temp) / stem / name))
                stack.enter_context(patch.object(cli, "probe", return_value="unreachable" if name == "database" else None))
                stack.enter_context(patch.object(cli, "load_env"))
                stack.enter_context(patch.object(cli.context, "load_user", return_value=SimpleNamespace(employee_id=6)))
                allowed = "allowed_run_as" if stem == "Weekly_pack" else "allowed_watch_run_as"
                stack.enter_context(patch.object(scheduling, allowed, return_value=name != "identity"))
                stack.enter_context(patch.object(cli, "graph", return_value=None))
                for method in ("route_graph", "ask_graph") if stem == "Weekly_pack" else ():
                    stack.enter_context(patch.object(cli, method, return_value=None))
                for method in ("pool", "saver"):
                    stack.enter_context(patch.object(cli.checkpointer, method, return_value=None))
                stack.enter_context(patch.object(scheduling, fire, side_effect=result if isinstance(result, Exception) else None,
                                                return_value=result))
                stack.enter_context(patch.object(monitoring, "init"))
                captured = stack.enter_context(patch.object(monitoring, "capture"))
                stack.enter_context(patch.object(monitoring, "_on", True))
                stack.enter_context(patch.object(monitoring, "_checkin",
                                                side_effect=lambda slug, status, *a, events=events: events.append(status)))
                stack.enter_context(patch.object(sys, "argv", [stem, "scheduled", "--as", "6"]))
                warning = stack.enter_context(patch.object(cli.logging.getLogger(cli.__name__), "warning"))
                with redirect_stdout(io.StringIO()):
                    try:
                        cli.main()
                    except SystemExit as stop:
                        assert stop.code == code, (stem, name, stop.code)
                    else:
                        raise AssertionError("scheduled CLI did not return its exit status")
                file = cli.LOG / ("scheduled.jsonl" if stem == "Weekly_pack" else "voyage_watch.jsonl")
                saved = json.loads(file.read_text(encoding="utf-8").splitlines()[-1])
                assert saved["exit"] == code
                if code in (4, 5):
                    assert saved["operational"]["outcome"] in ("failed", "degraded")
                    warning.assert_called_once()
                assert captured.call_count == int(name == "quota")
                assert events == (["in_progress", "error" if code else "ok"] if stem == "Weekly_pack" else [])
                assert not list(cli.LOG.glob("*.lock"))
                tested += 1
assert tested == 24
print("✅ Phase 2 validation passed. 24 actual CLI exits = durable logs; pack cron statuses agree, watch emits warnings.")

# %% Final Checkpoint
print("✅ Final Checkpoint: scheduler business outcomes verified; no live service calls or retained artifacts.")
