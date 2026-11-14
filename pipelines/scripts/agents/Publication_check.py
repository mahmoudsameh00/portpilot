"""Stabilization R9: complete publication, crash recovery, serialized reconciliation and visible sync state.

Run: uv run python tools/run.py pipelines/scripts/agents/Publication_check.py
Reads: code only. Writes: automatically removed temporary pack files. No database, network or model calls.
The real publisher node is exercised with rendering/DB stubs; existing V8 and DB integration stay separate.
Re-run: safe. Final Checkpoint: pipelines/checkpoints/agents/Publication_check.md.
"""
# %% Setup
import copy
import importlib.util
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists())
sys.path.insert(0, str(ROOT))
from filelock import FileLock, Timeout  # noqa: E402
from pipelines.agents import publications as pub, scheduling  # noqa: E402
from pipelines.agents.graphs import weekly_pack as wp  # noqa: E402
from pipelines.api.routers import packs  # noqa: E402


def payload(thread="pack:2025:23:1", summary="Approved summary"):
    deck = ("deck for " + thread).encode()
    run = {"report_week": 23, "thread_id": thread, "dataset": "live", "summary": [summary], "charts": {},
           "approved": {"at": "2026-11-11T10:00:00+00:00", "approver_employee_id": 6},
           "deck_sha256": pub.digest(deck)}
    return {"deck.pptx": deck, "run.json": pub.encoded(run), "deck_draft.json": pub.encoded({"title": summary}),
            "approval.json": pub.encoded([{"outcome": "approved"}])}


def noop():
    pass


with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    week = root / "2025-W23"
    first, second = payload(), payload("pack:2025:23:2", "New approved summary")

    # %% Phase 1 — Initial commit, DB failure and idempotent reconciliation
    stored = Mock(side_effect=RuntimeError("secret connection string must not reach the manifest"))
    manifest, folder = pub.publish(week, first, "input1", stored, noop)
    assert manifest["db_sync"]["status"] == "pending" and manifest["db_sync"]["attempts"] == 1
    assert set(p.name for p in folder.iterdir()) == pub.FILES
    assert "secret" not in (week / pub.POINTER).read_text(encoding="utf-8")
    assert pub.sync_status(week, "pack:2025:23:1") == "pending"
    repaired = Mock()
    synced = pub.reconcile(week, repaired)
    assert synced["db_sync"]["status"] == "synced" and synced["db_sync"]["attempts"] == 2
    assert repaired.call_args.args[0] == json.loads(first["run.json"])
    same, same_folder = pub.publish(week, first, "input1", repaired, noop)
    assert same_folder == folder and same == synced and repaired.call_count == 1
    pub.reconcile(week, repaired)
    assert repaired.call_count == 1
    print("✅ Phase 1 validation passed. Complete deck survives failed DB sync; durable pending state, safe retry and no-op replay.")

    # %% Phase 2 — Every failed publication boundary leaves one complete readable version
    original_replace = pub.os.replace
    for boundary in ("staging", "pointer"):
        def fail_replace(source, target, boundary=boundary):
            if (boundary == "staging" and Path(target).parent.name == "_publications") or (
                    boundary == "pointer" and Path(target).name == pub.POINTER):
                raise OSError("injected publication interruption")
            return original_replace(source, target)
        with patch.object(pub.os, "replace", side_effect=fail_replace):
            try:
                pub.publish(week, second, "input2", repaired, noop)
            except OSError:
                pass
            else:
                raise AssertionError("interruption was swallowed")
        visible, visible_folder = pub.current(week)
        assert visible == synced and visible_folder == folder
        assert (visible_folder / "deck.pptx").read_bytes() == first["deck.pptx"]
        assert not list(week.glob(".publishing-*")) and not list(week.glob(".manifest-*"))
    # A DB commit followed by a failed status write leaves pending; the same payload is replayed safely.
    calls = []
    original_atomic = pub.atomic_json
    def crash_after_db(path, value):
        if value["db_sync"]["status"] == "synced":
            raise OSError("crash after DB commit")
        original_atomic(path, value)
    with patch.object(pub, "atomic_json", side_effect=crash_after_db):
        try:
            pub.publish(week, second, "input2", calls.append, noop)
        except OSError:
            pass
        else:
            raise AssertionError("status-write failure was swallowed")
    pending, new_folder = pub.current(week)
    assert pending and pending["db_sync"]["status"] == "pending" and new_folder != folder
    pub.reconcile(week, calls.append)
    assert len(calls) == 2 and calls[0] == calls[1] == json.loads(second["run.json"])
    assert (folder / "deck.pptx").read_bytes() == first["deck.pptx"]
    print("✅ Phase 2 validation passed. Staging/pointer/after-DB crashes preserve complete packs and recover from saved approved content.")

    # %% Phase 3 — Mutual exclusion, corruption, legacy reads and API visibility
    with FileLock(str(week / ".publication.lock"), timeout=0):
        try:
            pub.reconcile(week, repaired)
        except Timeout:
            pass
        else:
            raise AssertionError("reconciliation bypassed an active publication lock")
    status = packs.publication_status({"published": {"week_folder": str(week)}}, "pack:2025:23:1")
    assert status == "superseded"
    assert packs.publication_status({"published": {"week_folder": str(week)}}, "pack:2025:23:2") == "synced"
    legacy = root / "legacy"
    legacy.mkdir()
    for name, data in first.items():
        (legacy / name).write_bytes(data)
    assert pub.current(legacy) == (None, legacy) and pub.sync_status(legacy) == "unknown"
    try:
        pub.reconcile(legacy, repaired)
    except ValueError as exc:
        assert "legacy" in str(exc)
    else:
        raise AssertionError("legacy rows were silently rewritten")
    (new_folder / "run.json").write_bytes(first["run.json"])
    try:
        pub.reconcile(week, repaired)
    except ValueError as exc:
        assert "integrity" in str(exc)
    else:
        raise AssertionError("corrupt approved payload reached the database")
    (new_folder / "run.json").write_bytes(second["run.json"])
    graph = SimpleNamespace(get_state=lambda cfg: None)
    entries = scheduling.report_entries(graph, [], root)
    assert len(entries) == 1 and entries[0]["thread_id"] == "pack:2025:23:2"
    print("✅ Phase 3 validation passed. Week lock, corruption refusal, legacy unknown state, superseded API status and report readers.")

    # %% Phase 4 — Real publisher node uses the protocol and keeps the old record on expiry
    node_root = root / "node"
    context = SimpleNamespace(user=SimpleNamespace(employee_id=6, role="manager", department="Finance"),
                              dataset="live", check_active=noop)
    runtime = SimpleNamespace(context=context)
    state = {"report_week": 23, "draft": {"title": "Draft for approval"}, "evidence": {}, "readiness": {},
             "verdict": {"ok": True}, "approval_log": [{"outcome": "approved", "at": "2026-11-11T10:00:00+00:00",
                                                         "approver_employee_id": 6}]}
    cfg = {"configurable": {"thread_id": "pack:2025:23:1"}}
    with patch.object(wp.v2, "render_draft", return_value={"bullets": [{"slide": 2, "text": "Approved summary"}]}), \
            patch.object(wp.render, "render", return_value=b"checked deck"), \
            patch.object(wp.readback, "validate_pptx", return_value=[]), \
            patch.object(wp, "is_live_reports", return_value=True), \
            patch.object(wp, "store_approved", side_effect=RuntimeError("DB unavailable")) as db:
        result = wp.make_publisher(node_root)(copy.deepcopy(state), cfg, runtime)
        assert result["status"] == "published" and result["published"]["db_sync"] == "pending"
        assert packs.publication_status(result, cfg["configurable"]["thread_id"]) == "pending"
        assert db.call_count == 1
        current_manifest, _ = pub.current(node_root / "2025-W23")
        context.check_active = Mock(side_effect=TimeoutError("expired"))
        try:
            wp.make_publisher(node_root)(copy.deepcopy(state), cfg, runtime)
        except TimeoutError:
            pass
        else:
            raise AssertionError("expired publisher continued")
        assert pub.current(node_root / "2025-W23")[0] == current_manifest
    print("✅ Phase 4 validation passed. Publisher integration retains pending sync visibly; expired work cannot replace the pack.")

    # %% Phase 5 — Reconciliation CLI enforces the existing approver rule and never invokes a model graph
    spec = importlib.util.spec_from_file_location("publication_cli", ROOT / "pipelines/scripts/agents/Weekly_pack.py")
    assert spec and spec.loader
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    cli.REPORTS = node_root
    for role, department, allowed in (("employee", "Finance", False), ("ceo", "Management", True),
                                      ("manager", "Finance", True), ("manager", "Operations", False)):
        user = SimpleNamespace(employee_id=6, role=role, department=department)
        with patch.object(wp.context, "load_user", return_value=user), patch.object(cli.monitoring, "init"), \
                patch.object(wp, "store_approved") as store, patch.object(cli, "graph") as graph_factory, \
                patch.object(sys, "argv", ["Weekly_pack", "reconcile", "--week", "23", "--as", "6"]), \
                redirect_stdout(io.StringIO()):
            try:
                cli.main()
            except SystemExit as stop:
                assert stop.code == 0 if allowed else "requires a Finance manager" in str(stop.code)
            else:
                raise AssertionError("reconciliation command did not return an exit status")
            if not allowed:
                store.assert_not_called()
            graph_factory.assert_not_called()
    assert pub.sync_status(node_root / "2025-W23") == "synced"
    print("✅ Phase 5 validation passed. Reconcile CLI allows Finance managers/CEO, refuses other roles, invokes no model graph.")

# %% Final Checkpoint
print("✅ Final Checkpoint: five publication phases passed; only temporary files, no live database or model calls.")
