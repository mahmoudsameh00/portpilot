"""The web's local-stack E2E fixture (Frontend plan §10.4, the done-when's "local-stack E2E, leakage 0").

Reads: the isolated full-data clone only (`PORTPILOT_API_TEST_DSN` + every `PG*` at 127.0.0.1:55432 /
portpilot_api_test, the guard of `integration_fixture`; the clone is made by `dev/tests/run_api_full_clone.ps1`).
Writes: on that clone, eight dedicated identities (`public.employees` 910001–910008, `web-stack-N@nilegate.com`) and
their `api.logins` (random passwords); the git-ignored `web/tests/stack/.fixture/people.json` (the identities and
passwords the Playwright suite reads). The upload test sends `clean_D1.pdf` of `Upload_fixtures.py` (read only).
`cleanup` deletes them again with every conversation, token, audit row and agent thread (`ask:` / `route_advice:` /
`arrival_advice:`) they made. Safe to re-run: `setup` first removes what an interrupted run left. Never touches
`ports-postgres`.

    uv run python dev/checks/api/Web_stack_fixture.py setup | cleanup
(normally called by `web/tests/stack/global-setup.ts` / `global-teardown.ts` through `dev/tests/run_web_stack.ps1`)
"""
import json
import os
import secrets
import sys
from pathlib import Path

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from dev.checks.api.integration_fixture import full_stack_guard, target  # noqa: E402

BASE = 910000
# the seven profiles of Api_check Phase 2 (ADR-006 by hand) + one more HR employee whose login the lockout test spends
PROFILES = [("employee", "Finance"), ("manager", "Finance"), ("employee", "Operations"), ("manager", "Operations"),
            ("employee", "HR"), ("manager", "HR"), ("ceo", "Operations"), ("employee", "HR")]
FIXTURE_DIR = ROOT / "web" / "tests" / "stack" / ".fixture"           # git-ignored
PEOPLE_FILE = FIXTURE_DIR / "people.json"
IDS = [BASE + n for n in range(1, len(PROFILES) + 1)]


def owner() -> psycopg.Connection:
    return psycopg.connect(make_conninfo(**target(os.environ.get("PORTPILOT_API_TEST_DSN"))), autocommit=True,
                           row_factory=dict_row)


def cleanup() -> dict:
    full_stack_guard()
    from pipelines.agents import checkpointer
    with owner() as oc:
        threads = [r["thread_id"] for r in oc.execute(
            "SELECT DISTINCT thread_id FROM agent_state.checkpoints WHERE thread_id LIKE 'ask:9100%%' "
            "OR thread_id LIKE 'route_advice:9100%%' OR thread_id LIKE 'arrival_advice:9100%%'")]
    saver = checkpointer.saver()
    for t in threads:
        saver.delete_thread(t)
    with owner() as oc:
        n = {"threads": len(threads),
             "conversations": oc.execute("DELETE FROM api.conversations WHERE employee_id = ANY(%s)", (IDS,)).rowcount,
             "audit": oc.execute("DELETE FROM api.audit_log WHERE employee_id = ANY(%s)", (IDS,)).rowcount,
             "tokens": oc.execute("DELETE FROM api.tokens WHERE employee_id = ANY(%s)", (IDS,)).rowcount,
             "logins": oc.execute("DELETE FROM api.logins WHERE employee_id = ANY(%s)", (IDS,)).rowcount,
             "employees": oc.execute("DELETE FROM public.employees WHERE employee_id = ANY(%s)", (IDS,)).rowcount}
    PEOPLE_FILE.unlink(missing_ok=True)
    return n


def setup() -> list[dict]:
    full_stack_guard()
    cleanup()
    from pipelines.api import passwords
    rows = []
    with owner() as oc, oc.transaction():
        for n, (role, dept) in enumerate(PROFILES, 1):
            identity, email = BASE + n, f"web-stack-{n}@nilegate.com"
            ins = oc.execute("INSERT INTO public.employees (employee_id, first_name, last_name, email, role_id, "
                             "department_id, hire_date) SELECT %s, 'Web', 'Stack', %s, r.role_id, d.department_id, "
                             "DATE '2025-01-01' FROM public.roles r CROSS JOIN public.departments d "
                             "WHERE r.role_name = %s AND d.department_name = %s", (identity, email, role, dept))
            assert ins.rowcount == 1, f"exactly one role / department for {role} / {dept}"
            password = secrets.token_urlsafe(24)
            oc.execute("INSERT INTO api.logins (employee_id, password_hash) VALUES (%s, %s)",
                       (identity, passwords.hash_password(password)))
            rows.append({"employee_id": identity, "email": email, "role": role, "dept": dept, "password": password,
                         "key": "lockout" if n == len(PROFILES) else f"{role}_{dept.lower()}"})
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    PEOPLE_FILE.write_text(json.dumps({"people": rows}, indent=1), encoding="utf-8", newline="\n")
    return rows


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "setup":
        print(f"web stack fixture: {len(setup())} identities on the clone, {PEOPLE_FILE.relative_to(ROOT)} written")
    elif cmd == "cleanup":
        print(f"web stack fixture removed: {cleanup()}")
    else:
        sys.exit("usage: Web_stack_fixture.py setup | cleanup")
