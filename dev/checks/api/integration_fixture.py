"""Disposable PostgreSQL fixtures. No .env fallback, no DROP, no production account reuse.

Only an explicitly supplied local port 55432 / portpilot_api_test database is accepted. Bootstrap requires
an empty database in a fresh PostgreSQL container. SQL constraints/grants come from the real migrations.
"""
import os
import re
import secrets
from pathlib import Path
from typing import LiteralString, cast

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg import sql

PROFILES = [("employee", "Finance"), ("manager", "Finance"), ("employee", "Operations"),
            ("manager", "Operations"), ("employee", "HR"), ("manager", "HR"), ("ceo", "Operations")]
DATABASE = "portpilot_api_test"


def target(raw: str | None) -> dict[str, str]:
    if not raw:
        raise ValueError("Set PORTPILOT_API_TEST_DSN explicitly; .env is never a test target")
    info = conninfo_to_dict(raw)
    if (info.get("dbname") != DATABASE or info.get("host") != "127.0.0.1" or info.get("port") != "55432"
            or set(info) - {"host", "port", "dbname", "user", "password"}
            or not info.get("user") or not info.get("password")):
        raise ValueError("Integration requires explicit credentials at 127.0.0.1:55432/portpilot_api_test only")
    return {**{key: str(value) for key, value in info.items()}, "connect_timeout": "5"}


def people(conn) -> list[dict]:
    """Dedicated identities also work in an isolated full-data clone; existing logins never matter."""
    rows = []
    for n, (role, dept) in enumerate(PROFILES, 1):
        identity, email = 900000 + n, f"api-test-{n}@nilegate.com"
        inserted = conn.execute("INSERT INTO public.employees (employee_id, first_name, last_name, email, role_id, "
                     "department_id, hire_date) SELECT %s, 'API', 'Fixture', %s, r.role_id, d.department_id, "
                     "DATE '2025-01-01' FROM public.roles r CROSS JOIN public.departments d "
                     "WHERE r.role_name = %s AND d.department_name = %s", (identity, email, role, dept))
        assert inserted.rowcount == 1, f"fixture requires exactly one role/department for {role}/{dept}"
        rows.append({"employee_id": identity, "email": email, "role": role, "dept": dept,
                     "password": secrets.token_urlsafe(24)})
    return rows


def bootstrap(root: Path, info: dict[str, str]) -> tuple[dict[str, str], list[dict]]:
    with psycopg.connect(make_conninfo(**info), autocommit=True) as conn:
        if conn.execute("SELECT tablename FROM pg_tables WHERE schemaname !~ '^pg_' "
                        "AND schemaname <> 'information_schema'").fetchall():
            raise ValueError("Fixture bootstrap requires an empty disposable database; nothing was changed")
        conn.execute("CREATE TABLE public.roles (role_id integer PRIMARY KEY, role_name text UNIQUE NOT NULL, "
                     "allowed_sensitivity_level integer NOT NULL); "
                     "CREATE TABLE public.departments (department_id integer PRIMARY KEY, "
                     "department_name text UNIQUE NOT NULL); "
                     "INSERT INTO public.roles VALUES (1, 'employee', 1), (2, 'manager', 2), (3, 'ceo', 3); "
                     "INSERT INTO public.departments VALUES (1, 'Finance'), (2, 'Operations'), (3, 'HR')")
        # Use the real employee table definition, including the compatibility email constraint.
        snapshot = (root / "db/schema_snapshot.sql").read_text(encoding="utf-8")
        employee = re.findall(r"CREATE TABLE public\.employees \(.*?\n\);", snapshot, re.S)
        assert len(employee) == 1
        conn.execute(sql.SQL(employee[0]))
        conn.execute("ALTER TABLE public.employees ADD PRIMARY KEY (employee_id); "
                     "CREATE SCHEMA agent_state; CREATE ROLE agent_writer NOLOGIN; "
                     "GRANT USAGE ON SCHEMA agent_state TO agent_writer; "
                     "ALTER DEFAULT PRIVILEGES IN SCHEMA agent_state GRANT SELECT, INSERT, UPDATE, DELETE "
                     "ON TABLES TO agent_writer")
        migration = (root / "db/migrations/023_api.sql").read_text(encoding="utf-8")
        original = "GRANT CONNECT ON DATABASE ports_logistics TO api_writer;"
        assert migration.count(original) == 1
        conn.execute(sql.SQL(cast(LiteralString, migration.replace(original, f"GRANT CONNECT ON DATABASE {DATABASE} TO api_writer;"))))
        # Only approved storage tables; the complete finance data/view acceptance stays a separate gate.
        approved = (root / "db/migrations/024_pack_approved.sql").read_text(encoding="utf-8")
        tables = re.findall(r"CREATE TABLE agent_state\.pack_approved(?:_summary)? \(.*?\n\);", approved, re.S)
        assert len(tables) == 2
        for statement in tables:
            conn.execute(sql.SQL(statement))
        rows = people(conn)
        runtime: dict[str, str] = {}
        for prefix, name, group in (("API", "portpilot_test_api", "api_writer"),
                                    ("RO", "portpilot_test_reader", None),
                                    ("AGENT", "portpilot_test_agent", "agent_writer")):
            password = secrets.token_urlsafe(24)
            conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(name), sql.Literal(password)))
            if group:
                conn.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(group), sql.Identifier(name)))
            runtime.update({f"PG_{prefix}_USER": name, f"PG_{prefix}_PASSWORD": password})
        conn.execute("GRANT SELECT ON public.employees, public.roles, public.departments TO portpilot_test_reader")
        runtime.update(PGHOST=info["host"], PGPORT=info["port"], PGDATABASE=info["dbname"],
                       PGUSER=info["user"], PGPASSWORD=info["password"])
    return runtime, rows


def full_stack_guard() -> None:
    """The old all-store suite must never silently use the normal application database again."""
    if os.environ.get("PORTPILOT_FULL_STACK_ISOLATED") != "1":
        raise RuntimeError("Api_check requires an isolated full-stack clone. See docs/api/integration_testing.md. "
                           "For deterministic PostgreSQL CI use Api_integration_check.py.")
    target(os.environ.get("PORTPILOT_API_TEST_DSN"))
    # Require the runtime target too: changing only the owner's connection would leave other pools on production.
    if (os.environ.get("PGDATABASE") != DATABASE or os.environ.get("PGHOST") != "127.0.0.1"
            or os.environ.get("PGPORT") != "55432"):
        raise RuntimeError("Every runtime pool must target the isolated PostgreSQL database")
