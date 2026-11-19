"""Isolated PostgreSQL integration (stabilization R10).

Reads code and migrations. Writes only the explicit disposable test database (port 55432); never reads .env.
Requires a fresh container for each run. No provider, MongoDB, Qdrant, live reports or live data calls.
Run through dev/tools/run.py after following docs/api/integration_testing.md. --guard-only is database-free.
"""
import os
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch
from typing import Any, cast

import psycopg
from psycopg.conninfo import make_conninfo
from fastapi.testclient import TestClient

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists())
sys.path.insert(0, str(ROOT))
from dev.checks.api.integration_fixture import bootstrap, full_stack_guard, target


def guards() -> None:
    valid = "host=127.0.0.1 port=55432 dbname=portpilot_api_test user=postgres password=test-only"
    for invalid in (None, "", valid.replace("55432", "5432"), valid.replace("portpilot_api_test", "ports_logistics"),
                    valid.replace("127.0.0.1", "remote"), valid + " options='-c search_path=public'", "service=normal"):
        try:
            target(invalid)
        except (ValueError, psycopg.Error):
            pass
        else:
            raise AssertionError("unsafe target accepted")
    assert target(valid)["dbname"] == "portpilot_api_test"
    # The historical full-store entry point also refuses implicit/live runtime pools without touching a DB.
    for env in ({}, {"PORTPILOT_FULL_STACK_ISOLATED": "1", "PORTPILOT_API_TEST_DSN": valid,
                     "PGHOST": "127.0.0.1", "PGPORT": "5432", "PGDATABASE": "ports_logistics"}):
        with patch.dict(os.environ, env, clear=True):
            try:
                full_stack_guard()
            except RuntimeError:
                pass
            else:
                raise AssertionError("full-store check accepted application defaults")
    print("✅ Phase 0: seven unsafe/implicit database targets refused before connection")


def integration(info: dict[str, str]) -> None:
    runtime, people = bootstrap(ROOT, info)
    # Disable dotenv before importing the app: no accidental model keys or unrelated store credentials.
    with patch.dict(os.environ, runtime, clear=True), patch("pipelines.lib.common.load_env", lambda *a, **kw: None):
        from pipelines.agents import checkpointer, locks
        from pipelines.agents.graphs.weekly_pack import store_approved
        from pipelines.agents.tools import db
        from pipelines.api import auth, passwords, store
        from pipelines.api.app import create_app

        try:
            with psycopg.connect(make_conninfo(**info), autocommit=True) as conn:
                for person in people:
                    conn.execute("INSERT INTO api.logins (employee_id, password_hash) VALUES (%s, %s)",
                                 (person["employee_id"], passwords.hash_password(person["password"])))
            app = create_app(roles_factory=cast(Any, lambda: (_ for _ in ()).throw(AssertionError("model called"))), access_log=None)
            with TestClient(app) as client:
                tokens = []
                for person in people:
                    login = client.post("/api/v1/auth/login", json={"email": person["email"], "password": person["password"]})
                    assert login.status_code == 200, login.status_code
                    body = login.json()
                    assert (body["me"]["role"], body["me"]["department"]) == (person["role"], person["dept"])
                    tokens.append(body["token"])
                headers = [{"Authorization": f"Bearer {token}"} for token in tokens]
                with psycopg.connect(make_conninfo(**info), autocommit=True) as conn:
                    saved = conn.execute("SELECT token_sha256 FROM api.tokens").fetchall()
                    assert {bytes(row[0]) for row in saved} == {auth.token_hash(token) for token in tokens}
                print("✅ Phase 1: seven deterministic identities sign in; only token hashes stored")

                conv = client.post("/api/v1/conversations", headers=headers[1])
                assert conv.status_code == 201
                url = "/api/v1/conversations/" + conv.json()["conversation_id"]
                assert client.get(url, headers=headers[1]).status_code == 200
                assert client.get(url, headers=headers[2]).status_code == 404
                assert client.get(url, headers=headers[6]).status_code == 200  # CEO read, never owner mutation
                assert client.delete(url, headers=headers[6]).status_code == 404
                assert client.delete(url, headers=headers[1]).status_code == 204
                # Real database permission boundaries, not mocked SQL.
                with store.pool().connection() as conn:
                    for statement in ("UPDATE api.logins SET password_hash = password_hash", "DELETE FROM api.audit_log"):
                        try:
                            conn.execute(statement)
                        except psycopg.errors.InsufficientPrivilege:
                            pass
                        else:
                            raise AssertionError("runtime write privilege too wide")
                print("✅ Phase 2: conversation ownership, CEO read-only access and runtime grants enforced")

                release = threading.Event()
                run = app.state.runner.submit(people[1]["employee_id"], "fixture", lambda r: (
                    release.wait(5), {"status": "answered", "answer": "Fixture result"})[1])
                run_url = "/api/v1/runs/" + run.id
                assert client.get(run_url, headers=headers[2]).status_code == 404
                release.set()
                deadline = time.monotonic() + 5
                while client.get(run_url, headers=headers[1]).json()["state"] not in ("done", "failed"):
                    assert time.monotonic() < deadline
                    time.sleep(0.01)
                result = client.get(run_url, headers=headers[1]).json()
                assert result["state"] == "done" and result["result"]["answer"] == "Fixture result"
                events = client.get(run_url + "/events", headers={**headers[1], "Last-Event-ID": "1"})
                ids = [int(line.split(":", 1)[1]) for line in events.text.splitlines() if line.startswith("id:")]
                assert events.status_code == 200 and "event: done" in events.text and ids and min(ids) > 1
                assert client.post("/api/v1/auth/logout", headers=headers[1]).status_code == 204
                assert client.get("/api/v1/me", headers=headers[1]).status_code == 401
                print("✅ Phase 3: owned run terminal result, SSE replay and token revocation")

            with locks.thread_lock("isolated:fixture"):
                try:
                    with locks.thread_lock("isolated:fixture"):
                        raise AssertionError("second connection acquired held lock")
                except locks.ThreadBusy:
                    pass
            with locks.thread_lock("isolated:fixture"):
                pass
            approval = {"approver_employee_id": people[1]["employee_id"]}
            thread = "weekly_pack:live:2025-W01:fixture"
            store_approved(1, thread, None, ["Saved summary"], approval, False)
            try:
                store_approved(1, thread, None, ["Replacement", ""], approval, False)
            except psycopg.errors.CheckViolation:
                pass
            else:
                raise AssertionError("invalid summary must roll back the replacement")
            with checkpointer.pool().connection() as conn:
                rows = conn.execute("SELECT text FROM agent_state.pack_approved_summary WHERE report_week = 1").fetchall()
                assert rows == [{"text": "Saved summary"}], rows
            store_approved(1, thread, None, ["Recovered summary"], approval, False)
            with checkpointer.pool().connection() as conn:
                rows = conn.execute("SELECT text FROM agent_state.pack_approved_summary WHERE report_week = 1").fetchall()
                assert rows == [{"text": "Recovered summary"}], rows
            print("✅ Phase 4: independent PostgreSQL lock connections; publication replacement rolls back and retries")
        finally:
            store.close()
            db.close()
            checkpointer.close()
    print("✅ Final Checkpoint: 5 / 5 phases; disposable database retained for inspection, no automatic deletion")


def main() -> None:
    guards()
    if "--guard-only" in sys.argv:
        return
    integration(target(os.environ.get("PORTPILOT_API_TEST_DSN")))


if __name__ == "__main__":
    main()
