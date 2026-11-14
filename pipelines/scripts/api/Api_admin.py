"""Manage the API's logins (FastAPI plan P1, owner A1): one login per employee, created by the owner only.

Commands (from the project root; the owner account of .env — PGUSER — because the API's own login cannot write a
password hash, migration 023):
    uv run python pipelines/scripts/api/Api_admin.py create --employee 13      a new login (password asked twice)
    uv run python pipelines/scripts/api/Api_admin.py reset --employee 13       a new password; its tokens revoked
    uv run python pipelines/scripts/api/Api_admin.py disable --employee 13     no sign-in; its tokens revoked
    uv run python pipelines/scripts/api/Api_admin.py enable --employee 13      sign-in again (failures cleared)
    uv run python pipelines/scripts/api/Api_admin.py list                      every login: employee, email, role, state
    add --password-stdin to create / reset to read the password from standard input (one line) instead of a prompt

Reads:   employees, roles, departments (who the login signs in as: the employee's email).
Writes:  api.logins, api.tokens (revocation), one api.audit_log row per change. Prints no password and no hash.
Re-run:  `create` refuses an employee that already has a login (use `reset`).
"""
import argparse
import getpass
import json
import os
import sys
from pathlib import Path

import psycopg

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from pipelines.api import passwords  # noqa: E402
from pipelines.lib.common import load_env  # noqa: E402


def connect():
    load_env(ROOT)
    e = os.environ
    return psycopg.connect(host=e["PGHOST"], port=e["PGPORT"], dbname=e["PGDATABASE"], user=e["PGUSER"],
                           password=e["PGPASSWORD"], autocommit=False)


def read_password(stdin: bool) -> str:
    if stdin:
        return sys.stdin.readline().rstrip("\r\n")
    first = getpass.getpass("password (≥ 12 characters): ")
    if getpass.getpass("again: ") != first:
        raise SystemExit("the two passwords differ: nothing changed")
    return first


def employee(conn, employee_id: int) -> dict:
    row = conn.execute("SELECT e.employee_id, e.email, r.role_name, d.department_name FROM employees e "
                       "JOIN roles r USING (role_id) JOIN departments d USING (department_id) "
                       "WHERE e.employee_id = %s", (employee_id,)).fetchone()
    if not row:
        raise SystemExit(f"no employee {employee_id}")
    return {"employee_id": row[0], "email": row[1], "role": row[2], "department": row[3]}


def audit(conn, employee_id: int, action: str) -> None:
    conn.execute("INSERT INTO api.audit_log (employee_id, resource_type, resource_id, action, decision, detail) "
                 "VALUES (%s, 'login', %s, %s, 'allowed', '{\"by\": \"Api_admin\"}')",
                 (employee_id, str(employee_id), action))


def revoke_tokens(conn, employee_id: int) -> int:
    return conn.execute("UPDATE api.tokens SET revoked_at = now() WHERE employee_id = %s AND revoked_at IS NULL",
                        (employee_id,)).rowcount


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("create", "reset", "disable", "enable"):
        s = sub.add_parser(name)
        s.add_argument("--employee", type=int, required=True)
        if name in ("create", "reset"):
            s.add_argument("--password-stdin", action="store_true")
    sub.add_parser("list")
    a = ap.parse_args()

    with connect() as conn:
        if a.cmd == "list":
            rows = conn.execute("SELECT l.employee_id, e.email, r.role_name, d.department_name, l.disabled, "
                                "l.locked_until > now(), l.password_set_at FROM api.logins l "
                                "JOIN employees e USING (employee_id) JOIN roles r USING (role_id) "
                                "JOIN departments d USING (department_id) ORDER BY 1").fetchall()
            for r in rows:
                state = "disabled" if r[4] else "locked" if r[5] else "active"
                print(f"{r[0]:>4}  {r[1]:<40} {r[2]:<9} {r[3]:<11} {state:<8} password set {r[6]:%Y-%m-%d}")
            print(f"{len(rows)} login(s)")
            return
        who = employee(conn, a.employee)
        exists = conn.execute("SELECT 1 FROM api.logins WHERE employee_id = %s", (a.employee,)).fetchone()
        out = {**who}
        if a.cmd == "create":
            if exists:
                raise SystemExit(f"employee {a.employee} already has a login: use `reset`")
            conn.execute("INSERT INTO api.logins (employee_id, password_hash) VALUES (%s, %s)",
                         (a.employee, passwords.hash_password(read_password(a.password_stdin))))
        elif not exists:
            raise SystemExit(f"employee {a.employee} has no login: use `create`")
        elif a.cmd == "reset":
            conn.execute("UPDATE api.logins SET password_hash = %s, password_set_at = now(), failed_attempts = 0, "
                         "locked_until = NULL WHERE employee_id = %s",
                         (passwords.hash_password(read_password(a.password_stdin)), a.employee))
            out["tokens_revoked"] = revoke_tokens(conn, a.employee)
        elif a.cmd == "disable":
            conn.execute("UPDATE api.logins SET disabled = true WHERE employee_id = %s", (a.employee,))
            out["tokens_revoked"] = revoke_tokens(conn, a.employee)
        else:
            conn.execute("UPDATE api.logins SET disabled = false, failed_attempts = 0, locked_until = NULL "
                         "WHERE employee_id = %s", (a.employee,))
        audit(conn, a.employee, f"admin_{a.cmd}")
        conn.commit()
    print(json.dumps({"done": a.cmd, **out}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
