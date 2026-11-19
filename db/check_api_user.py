"""Check the API's runtime login (member of api_writer, migration 023) from the host: password login through the
published port, search_path = api, every grant the runtime needs (inside rolled-back transactions), and everything
else refused — writing a password hash, creating or deleting a login, rewriting or deleting the audit log, DDL,
TRUNCATE, other schemas. Prints no credentials.
Run after db\\create_api_user.ps1:

    uv run python db/check_api_user.py

A throw-away login for one employee without a login is created first with the owner account (.env PGUSER) and
deleted at the end, so the token / conversation rows have a parent; the runtime's own rows are all rolled back.
"""
import hashlib
import os
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
e = os.environ
if not e.get("PG_API_USER") or not e.get("PG_API_PASSWORD"):
    raise SystemExit("PG_API_USER / PG_API_PASSWORD missing in .env: run db\\create_api_user.ps1 first")

results = []
denied = psycopg.errors.InsufficientPrivilege
CHECK_HASH = "scrypt$check$api$user$-$-"          # never a usable hash: no password signs in with it


def connect(user: str, password: str):
    return psycopg.connect(host=e["PGHOST"], port=e["PGPORT"], dbname=e["PGDATABASE"], user=user, password=password,
                           autocommit=True)


def refused(label: str, sql: str, params=None, expected=denied) -> None:
    try:
        with conn.transaction():
            conn.execute(sql, params)
        results.append((label, False, "ACCEPTED"))
    except expected as ex:
        results.append((label, True, type(ex).__name__))


class Rollback(Exception):
    pass


with connect(e["PGUSER"], e["PGPASSWORD"]) as owner:
    emp = owner.execute("SELECT min(employee_id) FROM employees WHERE employee_id NOT IN "
                        "(SELECT employee_id FROM api.logins)").fetchone()[0]
    owner.execute("INSERT INTO api.logins (employee_id, password_hash) VALUES (%s, %s)", (emp, CHECK_HASH))
try:
    with connect(e["PG_API_USER"], e["PG_API_PASSWORD"]) as conn:
        sp = conn.execute("SHOW search_path").fetchone()[0]
        results.append(("search_path = api", sp == "api", sp))
        tables = [r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'api' "
                                             "ORDER BY 1").fetchall()]
        want = ["audit_log", "conversation_turns", "conversations", "logins", "tokens"]
        results.append(("the five api tables exist", tables == want, ", ".join(tables) or "none"))
        h = conn.execute("SELECT password_hash FROM logins WHERE employee_id = %s", (emp,)).fetchone()
        results.append(("select api.logins (the hash)", h is not None and h[0] == CHECK_HASH, "1 row"))
        try:                                  # the runtime's whole write cycle, rolled back
            with conn.transaction():
                conn.execute("UPDATE logins SET failed_attempts = failed_attempts + 1, locked_until = now() "
                             "WHERE employee_id = %s", (emp,))
                tok = hashlib.sha256(b"check_api_user").digest()
                conn.execute("INSERT INTO tokens (token_sha256, employee_id, expires_at) "
                             "VALUES (%s, %s, now() + interval '8 hours')", (tok, emp))
                conn.execute("UPDATE tokens SET revoked_at = now() WHERE token_sha256 = %s", (tok,))
                cid = conn.execute("INSERT INTO conversations (employee_id) VALUES (%s) RETURNING conversation_id",
                                   (emp,)).fetchone()[0]
                conn.execute("UPDATE conversations SET last_turn_at = now(), closed_at = now() "
                             "WHERE conversation_id = %s", (cid,))
                conn.execute("INSERT INTO conversation_turns (conversation_id, turn_no, question, resolved_by, lang, "
                             "as_of, frame) VALUES (%s, 1, 'check', 'none', 'en', now(), '{\"vessel\": [36]}')", (cid,))
                conn.execute("UPDATE conversation_turns SET status = 'answered' WHERE conversation_id = %s", (cid,))
                conn.execute("DELETE FROM conversation_turns WHERE conversation_id = %s", (cid,))
                conn.execute("DELETE FROM conversations WHERE conversation_id = %s", (cid,))
                conn.execute("DELETE FROM tokens WHERE token_sha256 = %s", (tok,))
                n = conn.execute("INSERT INTO audit_log (employee_id, resource_type, action, decision) "
                                 "VALUES (%s, 'login', 'check', 'allowed') RETURNING id", (emp,)).fetchone()
                results.append(("runtime cycle: logins counters, tokens, conversations, turns, audit insert",
                                n is not None, "rolled back"))
                raise Rollback
        except Rollback:
            pass
        refused("write a password hash refused", "UPDATE logins SET password_hash = 'scrypt$x' WHERE employee_id = %s",
                (emp,))
        refused("disable a login refused", "UPDATE logins SET disabled = true WHERE employee_id = %s", (emp,))
        refused("create a login refused", "INSERT INTO logins (employee_id, password_hash) VALUES (%s, 'scrypt$x')",
                (emp,))
        refused("delete a login refused", "DELETE FROM logins WHERE employee_id = %s", (emp,))
        refused("rewrite a token's expiry refused", "UPDATE tokens SET expires_at = now()")
        refused("update api.audit_log refused", "UPDATE audit_log SET decision = 'allowed'")
        refused("delete api.audit_log refused", "DELETE FROM audit_log")
        refused("create table in api refused", "CREATE TABLE api.x (i int)")
        refused("truncate api.tokens refused", "TRUNCATE api.tokens")
        refused("drop api.logins refused", "DROP TABLE api.logins")
        for table in ["public.employees", "public.invoices", "finance.kpi_weekly", "agent_state.checkpoints",
                      "agent_state.llm_daily_usage"]:
            refused(f"select {table} refused", f"SELECT 1 FROM {table} LIMIT 1")
        refused("create table in public refused", "CREATE TABLE public.x (i int)")
finally:
    with connect(e["PGUSER"], e["PGPASSWORD"]) as owner:
        gone = owner.execute("DELETE FROM api.logins WHERE employee_id = %s AND password_hash = %s",
                             (emp, CHECK_HASH)).rowcount
    results.append(("throw-away login removed", gone == 1, f"{gone} row"))
for label, ok, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {label}: {detail}")
raise SystemExit(0 if all(ok for _, ok, _ in results) else 1)
