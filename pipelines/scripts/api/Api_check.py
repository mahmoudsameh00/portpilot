"""API check (FastAPI plan §10): the contract of `pipelines/api/`, phase by phase as the plan's phases add it.

Plan:    docs/archive/2026-11-05_FastAPI_plan.md (approved 2026-11-03).
Run:     uv run python tools/run.py pipelines/scripts/api/Api_check.py  (from the project root; ≈ 1 minute: every
         sign-in costs one scrypt hash, ≈ 2 s)

Reads:   the databases through the API (FastAPI's TestClient calls the app in process; no LLM, no network beyond the
         local stores).
Writes:  dedicated fixture employees/logins in an explicitly isolated full-stack clone (never the normal .env DB),
         their tokens (cascade) and the audit rows they caused (deleted at the end, owner account). Nothing tracked.
Re-run:  after cleanup; see docs/api/integration_testing.md. No automatic live-store fallback.

Phases
0. Skeleton (P0): the factory builds a fresh app; `GET /api/v1/health/live` → 200; an unknown path → 404; every route
   of the OpenAPI schema is under the base path; `Serve.py` binds 127.0.0.1 with one process.
1. Auth (P3): sign-in → a token whose SHA-256 alone is stored; `/me` = the employee's role and department from
   PostgreSQL; the same 401 body (and about the same time) for an unknown email and a wrong password; 5 wrong
   passwords lock the login (the right one is refused too); sign-out revokes; an expired token, a disabled login, a
   missing or malformed header → 401 with `WWW-Authenticate: Bearer`; every sign-in in `audit_log` with its request
   id; `/health/ready` with a token → every store up, without → 401.
2. RBAC (P3 part: `/me`): seven access profiles (employee / manager × Finance / Operations / HR + the CEO) → the
   products and tools of ADR-006, written here by hand. The IDOR part (threads, runs, conversations) joins in P4–P6.
3. Error mapping (P3): every row of plan §7 provoked — 404, 405, 422 without the input echoed, 413 declared and
   chunked, `Exhausted` → 503 + Retry-After, database down / pool busy → 503, an unexpected exception → an opaque
   500 (its text never sent); every body problem+json with the request id.
4. Event contract (P4, fake models): a question's SSE stream = `queued`, `started`, … , `answer`, `done` with
   increasing ids; every event and field inside `schemas.EVENT_FIELDS` (no tool arguments, no rows); node names on the
   allowlist, tool names among the routed tools; `Last-Event-ID` replays only what follows; `GET /runs/{id}` = the
   stream's answer; a refused question → `tool_refused` + `not_permitted` with 0 model calls; the API's answer = the
   same question through `sv.ask` directly.
5. Ask, concurrency, isolation (P4, fake models): the POST returns before a slow run ends (C7); one run per
   conversation (409); a thread lock held → 409 (C5); a full queue and the per-employee limit → 429 + Retry-After
   (C8); a run past its time limit → `failed` 504; the event loop answers while 4 runs are busy (C9); 50 questions at
   once → 24 accepted (4 slots + 20 queued), 26 × 429, 0 × 500; another employee gets 404 on a run, its events, a
   stored answer and a conversation, the CEO reads but cannot continue them.
6. Uploads (P5): the fixtures' verdicts through HTTP (a clean PDF accepted, an attack accepted with its section
   removed, two shapes refused as 422 problems with their codes); the question's document tool returns the upload as
   its own rows labelled `untrusted_upload`; owner-only (another employee 404, the CEO reads the list only); an upload
   holds the conversation busy (409); promotion: an employee 403, a manager's clean upload filed (its folder removed
   again), a screened one refused; delete and close empty the memory.
7. The weekly pack (P6, fake models, a test thread `weekly_pack:apicheck:…` in a temp reports folder — never the
   scheduler's `live` replay): list / show / preview for a Finance reader, 403 for an operations employee; a decision by
   a Finance employee 403; an edit by the Finance manager → re-validated, `approval_needed`; approve → published, the
   deck downloads; a second decision → 409; the run keeps its identity (the approver only decides).
8. Route advice + the watch (P6): a no-Suez route answered with 0 model calls through the run executor; the stored
   advice for its asker and the CEO, 404 for another employee; the saved watch alerts and runs for every employee.
9. Security headers, CORS, limits (P3): the headers on 200 / 401 / 404 / 500; a client's UUID request id echoed, a
   malformed one replaced; the docs page's own CSP; CORS for the configured origin only, no credentials; `*`
   refused as an origin.
10. The chart catalogue and the smart view (approver-additions plan Phase F): the catalogue; a view by choice = the
   tool's values; RBAC 403; 422 shapes; a question → one fake structured call → the same view; no week → ask back.
   (Phase 7 also covers the plan's Phase E: chart variants + an addition, 422 mixes, a revise through the API.)
Final Checkpoint (pending phases listed).
"""
# %% Setup
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient
from psycopg.rows import dict_row
from psycopg_pool import PoolTimeout

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from pipelines.scripts.api.integration_fixture import full_stack_guard, people as fixture_people, target  # noqa: E402

full_stack_guard()                       # before importing the app or opening any pool
from langchain_core.messages import AIMessage, ToolMessage  # noqa: E402

from pipelines.agents import approver_request as ar_mod  # noqa: E402
from pipelines.agents import checkpointer, llm, roles  # noqa: E402
from pipelines.agents.deck import sample  # noqa: E402
from pipelines.agents.graphs import models as gm  # noqa: E402
from pipelines.agents.graphs import supervisor as sv  # noqa: E402
from pipelines.agents.graphs import weekly_pack as wp  # noqa: E402
from pipelines.agents.tools import context as ctx_mod  # noqa: E402
from pipelines.api import app as app_mod  # noqa: E402
from pipelines.api import auth, config, middleware, passwords, runs, schemas  # noqa: E402
from pipelines.api.errors import ApiError  # noqa: E402
from pipelines.lib import session_store  # noqa: E402

DONE: list[int] = []
B = app_mod.BASE
SECURITY_HEADERS = {"x-content-type-options": "nosniff", "x-frame-options": "DENY", "referrer-policy": "no-referrer",
                    "cache-control": "no-store"}


def owner():
    from psycopg.conninfo import make_conninfo
    return psycopg.Connection[dict].connect(make_conninfo(**target(os.environ.get("PORTPILOT_API_TEST_DSN"))),
                           autocommit=True, row_factory=dict_row)


def headers_ok(r) -> bool:
    return all(r.headers.get(k) == v for k, v in SECURITY_HEADERS.items()) and "content-security-policy" in r.headers


def is_problem(r, status: int) -> bool:
    body = r.json()
    return (r.status_code == status and r.headers.get("content-type", "").startswith("application/problem+json")
            and body.get("status") == status and {"type", "title", "status", "detail", "request_id"} <= set(body)
            and set(body) - {"type", "title", "status", "detail", "request_id"} <= {"upload", "problems"}
            and body["request_id"] == r.headers.get("x-request-id"))


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# %% Phase 0 — the skeleton
a, b = app_mod.create_app(access_log=None), app_mod.create_app(access_log=None)
assert a is not b, "the factory must build a fresh app each call"
with TestClient(a) as client:
    r = client.get(f"{B}/health/live")
    assert r.status_code == 200 and r.json() == {"status": "live"}, (r.status_code, r.text[:200])
    assert client.get(f"{B}/no-such-route").status_code == 404
    assert client.get("/health/live").status_code == 404, "a route outside the base path"
    paths = sorted(client.get("/openapi.json").json()["paths"])
assert paths and all(p.startswith(B + "/") for p in paths), paths
spec = importlib.util.spec_from_file_location("serve", ROOT / "pipelines" / "scripts" / "api" / "Serve.py")
assert spec and spec.loader
serve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve)                      # `main()` is not called: nothing is served
src = (ROOT / "pipelines" / "scripts" / "api" / "Serve.py").read_text(encoding="utf-8")
assert serve.HOST == "127.0.0.1" and "workers=1" in src and "factory=True" in src
DONE.append(0)
print(f"✅ Phase 0 validation passed: fresh app per call; health/live 200; unknown 404; {len(paths)} route(s), all "
      f"under {B}; Serve.py on {serve.HOST}, one process")


# %% Setup for Phases 1–3 and 9 — seven dedicated identities in the isolated clone
PROFILES = [("employee", "Finance"), ("manager", "Finance"), ("employee", "Operations"), ("manager", "Operations"),
            ("employee", "HR"), ("manager", "HR"), ("ceo", "Operations")]
started_at = datetime.now(timezone.utc)
with owner() as oc:
    with oc.transaction():
        fixtures = fixture_people(oc)
PEOPLE: dict[tuple[str, str], dict] = {(row["role"], row["dept"]): row for row in fixtures}
assert set(PEOPLE) == set(PROFILES)
CHECK_IDS = [PEOPLE[p]["employee_id"] for p in PROFILES]
with owner() as oc:
    for p in PROFILES:
        oc.execute("INSERT INTO api.logins (employee_id, password_hash) VALUES (%s, %s)",
                   (PEOPLE[p]["employee_id"], passwords.hash_password(PEOPLE[p]["password"])))
auth._dummy_hash()                                  # computed once, before the timing comparison of Phase 1


THREADS: list[str] = []                             # the ask threads this run creates (deleted at the end)


def cleanup() -> tuple[int, int, int]:
    saver = checkpointer.saver()
    for t in THREADS:
        saver.delete_thread(t)
    with owner() as oc:
        n_audit = oc.execute("DELETE FROM api.audit_log WHERE at >= %s AND (employee_id = ANY(%s) OR employee_id IS "
                             "NULL)", (started_at, CHECK_IDS)).rowcount
        oc.execute("DELETE FROM api.conversations WHERE employee_id = ANY(%s)", (CHECK_IDS,))
        n_logins = oc.execute("DELETE FROM api.logins WHERE employee_id = ANY(%s)", (CHECK_IDS,)).rowcount
        oc.execute("DELETE FROM public.employees WHERE employee_id = ANY(%s)", (CHECK_IDS,))
    return n_logins, n_audit, len(THREADS)


class Fake:
    """The supervisor's model for Phases 4–6: one tool call (`voyage_status`, or `search_documents` for the upload
    phase), then a `not_in_data` answer; `delay` keeps a run busy (C7–C9)."""
    delay = 0.0
    call = ("voyage_status", {"vessel_id": 234})

    def __call__(self, role, msgs, tools, schema):
        time.sleep(self.delay)
        if not any(isinstance(m, ToolMessage) and m.name not in (sv.SKILL_TOOL, sv.ANSWER_TOOL) for m in msgs):
            return AIMessage(content="", tool_calls=[{"name": self.call[0], "args": self.call[1], "id": "c1"}])
        return AIMessage(content="", tool_calls=[{"name": sv.ANSWER_TOOL, "args": {
            "status": "not_in_data", "answer": "This is not in PortPilot's data.", "evidence_ids": []}, "id": "a1"}])


FAKE = Fake()
Q_OPS = "Where is Cruise Voyager 234 now?"
Q_FIN = "How much did we bill in week 23 of 2025?"
ACCESS_LOG = Path(tempfile.mkdtemp(prefix="api_check_log_")) / "api.jsonl"
app = app_mod.create_app(roles_factory=lambda: roles.FakeRoles(FAKE), access_log=ACCESS_LOG)
client = TestClient(app, raise_server_exceptions=False)
client.__enter__()


def events_of(url: str, token: str, last: int | None = None) -> list[tuple[int, str, dict]]:
    h = {**bearer(token), **({"Last-Event-ID": str(last)} if last is not None else {})}
    out, cur = [], {}
    with client.stream("GET", url, headers=h) as s:
        assert s.status_code == 200 and s.headers["content-type"].startswith("text/event-stream"), s.status_code
        for line in s.iter_lines():
            if line.startswith("id:"):
                cur["id"] = int(line[3:].strip())
            elif line.startswith("event:"):
                cur["event"] = line[6:].strip()
            elif line.startswith("data:"):
                cur["data"] = json.loads(line[5:].strip())
            elif not line and cur:
                out.append((cur["id"], cur["event"], cur["data"]))
                cur = {}
    return out


def ask(token: str, question: str, conversation: str | None = None):
    conv = conversation or client.post(f"{B}/conversations", headers=bearer(token)).json()["conversation_id"]
    r = client.post(f"{B}/conversations/{conv}/questions", json={"question": question}, headers=bearer(token))
    if r.status_code == 202:
        THREADS.append(r.json()["thread_id"])
    return r, conv


def settle(timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while any(not x.finished for x in app.state.runner.runs.values()) and time.monotonic() < deadline:
        time.sleep(0.2)


def login(profile, password: str | None = None, rid: str | None = None):
    who = PEOPLE[profile]
    return client.post(f"{B}/auth/login", json={"email": who["email"], "password": password or who["password"]},
                       headers={"X-Request-ID": rid} if rid else None)


try:
    # %% Phase 1 — auth
    FM = ("manager", "Finance")
    rid = str(uuid.uuid4())
    r = login(FM, rid=rid)
    assert r.status_code == 200 and r.headers["x-request-id"] == rid, (r.status_code, r.text[:300])
    tok = r.json()["token"]
    me = client.get(f"{B}/me", headers=bearer(tok)).json()
    assert (me["employee_id"], me["role"], me["department"]) == (PEOPLE[FM]["employee_id"], "manager", "Finance"), me
    with owner() as oc:
        stored = oc.execute("SELECT count(*) AS n FROM api.tokens WHERE token_sha256 = %s",
                            (hashlib.sha256(tok.encode()).digest(),)).fetchone()["n"]
        plain = oc.execute("SELECT count(*) AS n FROM api.tokens WHERE encode(token_sha256, 'escape') = %s",
                           (tok,)).fetchone()["n"]
    assert (stored, plain) == (1, 0), (stored, plain)

    t0 = time.perf_counter()
    unknown = client.post(f"{B}/auth/login", json={"email": "nobody@nilegate.com", "password": "x" * 14})
    t_unknown = time.perf_counter() - t0
    t0 = time.perf_counter()
    wrong = login(("employee", "Finance"), password="not-the-password")
    t_wrong = time.perf_counter() - t0

    def body_wo_id(r):
        return {k: v for k, v in r.json().items() if k != "request_id"}
    assert is_problem(unknown, 401) and is_problem(wrong, 401) and body_wo_id(unknown) == body_wo_id(wrong)
    assert unknown.headers.get("www-authenticate") == "Bearer"
    assert 0.5 < t_unknown / t_wrong < 2.0, (t_unknown, t_wrong)

    LOCKED = ("employee", "HR")
    for _ in range(config.MAX_FAILURES):
        assert login(LOCKED, password="wrong-password-x").status_code == 401
    locked = login(LOCKED)
    assert is_problem(locked, 401) and body_wo_id(locked) == body_wo_id(wrong), locked.text

    OE = ("employee", "Operations")
    tok_oe = login(OE).json()["token"]
    assert client.post(f"{B}/auth/logout", headers=bearer(tok_oe)).status_code == 204
    assert is_problem(client.get(f"{B}/me", headers=bearer(tok_oe)), 401)
    tok_exp = login(OE).json()["token"]
    with owner() as oc:
        oc.execute("UPDATE api.tokens SET issued_at = now() - interval '9 hours', expires_at = now() - interval "
                   "'1 hour' WHERE token_sha256 = %s", (hashlib.sha256(tok_exp.encode()).digest(),))
    assert is_problem(client.get(f"{B}/me", headers=bearer(tok_exp)), 401)
    DIS = ("manager", "HR")
    tok_dis = login(DIS).json()["token"]
    with owner() as oc:
        oc.execute("UPDATE api.logins SET disabled = true WHERE employee_id = %s", (PEOPLE[DIS]["employee_id"],))
    assert is_problem(client.get(f"{B}/me", headers=bearer(tok_dis)), 401) and is_problem(login(DIS), 401)
    for h in ({}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer "}, bearer("not-a-token")):
        r = client.get(f"{B}/me", headers=h)
        assert is_problem(r, 401) and r.headers.get("www-authenticate") == "Bearer", (h, r.text)

    with owner() as oc:
        rows = oc.execute("SELECT employee_id, action, decision, request_id::text AS rid, detail FROM api.audit_log "
                          "WHERE at >= %s ORDER BY id", (started_at,)).fetchall()
    signin = [x for x in rows if x["action"] == "sign_in"]
    assert any(x["rid"] == rid and x["decision"] == "allowed" for x in signin), "the sign-in with its request id"
    reasons = {x["detail"].get("reason") for x in signin if x["decision"] == "denied"}
    assert {"no_login", "wrong_password", "locked", "disabled"} <= reasons, reasons
    assert any(x["action"] == "sign_out" for x in rows)
    assert not any(PEOPLE[p]["password"] in json.dumps(x, default=str) for x in rows for p in PROFILES)

    ready = client.get(f"{B}/health/ready", headers=bearer(tok))
    assert ready.status_code == 200 and ready.json()["status"] == "ready", ready.text
    assert is_problem(client.get(f"{B}/health/ready"), 401)
    DONE.append(1)
    print(f"✅ Phase 1 validation passed: sign-in → token (only its SHA-256 stored), /me from PostgreSQL; unknown email "
          f"= wrong password (same 401 body, {t_unknown:.1f} s vs {t_wrong:.1f} s); lock after {config.MAX_FAILURES}; "
          f"sign-out, expiry, disabled, bad headers → 401; {len(signin)} sign-ins audited (no password); ready "
          f"{len(ready.json()['components'])} / {len(ready.json()['components'])} up")

    # %% Phase 2 — RBAC of /me (ADR-006 by hand)
    FINANCE_TOOLS = {"finance_kpi", "invoice_audit"}
    reads_finance = {("employee", "Finance"): True, ("manager", "Finance"): True, ("employee", "Operations"): False,
                     ("manager", "Operations"): True, ("employee", "HR"): False, ("manager", "HR"): True,
                     ("ceo", "Operations"): True}
    decides = {("manager", "Finance"), ("ceo", "Operations")}
    with owner() as oc:                             # the profiles locked / disabled in Phase 1 sign in again
        oc.execute("UPDATE api.logins SET disabled = false, failed_attempts = 0, locked_until = NULL "
                   "WHERE employee_id = ANY(%s)", (CHECK_IDS,))
    seen = {}
    for p in PROFILES:
        m = client.get(f"{B}/me", headers=bearer(login(p).json()["token"])).json()
        pr = m["products"]
        assert (m["role"], m["department"]) == p, (p, m)
        assert pr["packs_read"] == reads_finance[p] and pr["packs_decide"] == (p in decides), (p, pr)
        assert (FINANCE_TOOLS <= set(m["tools"])) == reads_finance[p], (p, m["tools"])
        assert pr["ask"] and pr["route_advice"] and pr["voyage_watch"] and "search_documents" in m["tools"], (p, m)
        seen[p] = (pr["packs_read"], pr["packs_decide"])
    DONE.append(2)
    print(f"✅ Phase 2 validation passed: /me of {len(seen)} profiles = ADR-006 by hand (packs read by Finance + every "
          "manager + the CEO, decided by the Finance manager + the CEO; finance tools only where finance is "
          "readable); the IDOR matrix of threads / runs / conversations joins in P4–P6")

    # %% Phase 3 — error mapping
    def boom_quota():
        raise llm.Exhausted("check")

    def boom_db():
        raise psycopg.OperationalError("connection refused (check)")

    def boom_pool():
        raise PoolTimeout("check")

    SECRET = "gsk_CHECK_ONLY_secret_in_an_exception"

    def boom():
        raise RuntimeError(SECRET)
    for path, fn in (("quota", boom_quota), ("db", boom_db), ("pool", boom_pool), ("boom", boom)):
        app.add_api_route(f"{B}/_check/{path}", fn, methods=["GET"])
    r404, r405 = client.get(f"{B}/nothing-here"), client.post(f"{B}/health/live")
    pw = "P@ss-SECRET-in-a-bad-body-123"
    r422 = client.post(f"{B}/auth/login", json={"password": pw, "role": "ceo"})
    big = "x" * (config.MAX_BODY_BYTES + 1)
    r413 = client.post(f"{B}/auth/login", content=big, headers={"Content-Type": "application/json"})
    r413c = client.post(f"{B}/auth/login", content=(c for c in [big[:9000].encode(), big[9000:].encode()]),
                        headers={"Content-Type": "application/json"})
    rq, rdb, rpool, r500 = (client.get(f"{B}/_check/{p}") for p in ("quota", "db", "pool", "boom"))
    assert is_problem(r404, 404) and is_problem(r405, 405)
    assert is_problem(r422, 422) and pw not in r422.text and "extra" in r422.text.lower(), r422.text
    assert is_problem(r413, 413) and is_problem(r413c, 413), (r413.status_code, r413c.status_code, r413c.text[:200])
    assert is_problem(rq, 503) and rq.headers.get("retry-after"), rq.text
    assert is_problem(rdb, 503) and is_problem(rpool, 503) and rdb.headers.get("retry-after")
    assert is_problem(r500, 500) and SECRET not in r500.text and "RuntimeError" not in r500.text, r500.text
    DONE.append(3)
    print("✅ Phase 3 validation passed: 404 / 405 / 422 (input not echoed, an unknown field refused) / 413 declared "
          "and chunked / quota 503 + Retry-After / database 503 / pool 503 / opaque 500 — every body problem+json "
          "with the request id")

    # %% Phase 4 — the event contract
    tok_ops = login(("employee", "Operations")).json()["token"]
    acc, conv_ops = ask(tok_ops, Q_OPS)
    assert acc.status_code == 202, acc.text
    ev = events_of(acc.json()["events_url"], tok_ops)
    names = [e for _, e, _ in ev]
    ids = [i for i, _, _ in ev]
    assert names[:2] == ["queued", "started"] and names[-2:] == ["answer", "done"], names
    assert ids == list(range(1, len(ids) + 1)), ids
    for _, e, d in ev:
        assert e in schemas.EVENT_FIELDS and set(d) <= schemas.EVENT_FIELDS[e], (e, sorted(d))
    nodes = {d["name"] for _, e, d in ev if e == "node"}
    tools_called = [d["name"] for _, e, d in ev if e == "tool_called"]
    ops_user = ctx_mod.load_user(PEOPLE[("employee", "Operations")]["employee_id"])
    routed = sv.route(Q_OPS, ops_user).tools
    assert nodes and nodes <= {"model", "tools"} and tools_called == ["voyage_status"] and \
        set(tools_called) <= set(routed), (nodes, tools_called, routed)
    assert "234" not in json.dumps([d for _, e, d in ev if e != "answer"]), "a tool argument leaked into an event"
    answer = next(d for _, e, d in ev if e == "answer")
    replay = events_of(acc.json()["events_url"], tok_ops, last=ids[-3])
    assert [i for i, _, _ in replay] == ids[-2:], [i for i, _, _ in replay]
    run_doc = client.get(acc.json()["run_url"], headers=bearer(tok_ops)).json()
    assert run_doc["state"] == "done" and run_doc["result"] == answer and len(run_doc["events"]) == len(ev)
    acc2, _ = ask(tok_ops, Q_FIN)
    ev2 = events_of(acc2.json()["events_url"], tok_ops)
    refused = [d for _, e, d in ev2 if e == "tool_refused"]
    ans2 = next(d for _, e, d in ev2 if e == "answer")
    assert refused and refused[0]["name"] == "finance_kpi" and ans2["status"] == "not_permitted" and \
        ans2["model_calls"] == 0, (refused, ans2)
    direct_graph = sv.build_graph(roles.FakeRoles(FAKE), checkpointer.saver(), saver=checkpointer.saver(),
                                  pool=checkpointer.pool())
    direct_tid = f"check:api:{uuid.uuid4().hex[:8]}"
    THREADS.append(direct_tid)
    direct = sv.answer_summary(sv.ask(direct_graph, Q_OPS, ops_user, thread=direct_tid))
    strip = lambda d: {k: v for k, v in d.items() if k != "thread"}   # noqa: E731
    typed = schemas.AnswerData.model_validate(direct).model_dump(mode="json")     # the API's one typed shape (F0)
    assert strip(typed) == strip(answer), (typed, answer)
    DONE.append(4)
    print(f"✅ Phase 4 validation passed: {len(ev)} events in order (queued → started → node / tool_called → answer → "
          f"done), every field in the contract, nodes {sorted(nodes)}, tools {tools_called} (no argument); "
          f"Last-Event-ID replays the tail; GET /runs = the stream; a refused question → tool_refused + not_permitted "
          f"with 0 model calls; the API's answer = sv.ask directly")

    # %% Phase 5 — ask, concurrency (C5, C7–C9), isolation
    FAKE.delay = 1.5
    t0 = time.perf_counter()
    slow, conv_slow = ask(tok_ops, Q_OPS)
    post_s = time.perf_counter() - t0
    busy, _ = ask(tok_ops, Q_OPS, conversation=conv_slow)
    assert slow.status_code == 202 and post_s < 0.5, (slow.status_code, post_s)
    assert is_problem(busy, 409), busy.text
    lock_err = {}
    with runs.thread_lock("check:api:lock"):
        def second():
            try:
                with runs.thread_lock("check:api:lock"):
                    pass
            except ApiError as exc:
                lock_err["status"] = exc.status
        th = threading.Thread(target=second)
        th.start()
        th.join()
    assert lock_err.get("status") == 409, lock_err
    settle()

    # end order (D-F2): record → free the conversation → publish; a private runner, no model, no database
    def end_order(work, timeout: float | None = None, fail_record: bool = False) -> tuple[list, runs.Run]:
        rn, seen, holder = runs.Runner(slots=1, queue=1), [], []
        if timeout is not None:
            runs.TIMEOUT_S["check_end"] = timeout

        def record(state, result):
            seen.append((state, result, holder[0].finished, "c:end" in rn._busy_conversations,
                         [e.event for e in holder[0].since(0)]))
            if fail_record:
                raise RuntimeError("record lost")
        def held(run):                                  # the run is known before `record` (a fast work ends
            holder.append(run)                          # before `submit` returns)
            return work(run)
        try:
            rn.submit(0, "check_end", held, conversation_id="c:end", on_finish=record)
            rn.pool.shutdown(wait=True)                 # the run's thread has ended: everything is published
        finally:
            runs.TIMEOUT_S.pop("check_end", None)
        assert "c:end" not in rn._busy_conversations and holder[0].finished
        return seen, holder[0]

    seen, r_ok = end_order(lambda run: {"status": "answered"})
    # since stabilization R-contract the runner records the answer as the AnswerData contract fills it (defaults in)
    full = schemas.AnswerData.model_validate({"status": "answered"}).model_dump(mode="json")
    assert seen == [("done", full, False, True, ["queued", "started"])], seen
    assert [e.event for e in r_ok.since(0)][-2:] == ["answer", "done"]
    seen, r_err = end_order(lambda run: 1 / 0)
    assert seen[0][:4] == ("failed", None, False, True) and r_err.error and r_err.error["status"] == 500, seen
    seen, r_slow = end_order(lambda run: time.sleep(0.6) or {"status": "answered"}, timeout=0.15)
    assert seen[0][:3] == ("failed", None, True) and seen[0][4][-1] == "failed", seen   # told first, recorded after
    assert "answer" not in [e.event for e in r_slow.since(0)] and r_slow.error["status"] == 504
    _, r_lost = end_order(lambda run: {"status": "answered"}, fail_record=True)
    # since stabilization (runs.py "a lost record is a visible failure"): the run ends failed, 500 record_failed,
    # instead of a "done" whose end nobody stored
    assert r_lost.state == "failed" and [e.event for e in r_lost.since(0)][-1] == "failed" and \
        r_lost.error and r_lost.error["status"] == 500 and "record_failed" in json.dumps(r_lost.error), r_lost.error

    lags = []
    for _ in range(4):
        ask(tok_ops, Q_OPS)
    for _ in range(5):
        t0 = time.perf_counter()
        assert client.get(f"{B}/health/live").status_code == 200
        lags.append(time.perf_counter() - t0)
    assert max(lags) < 0.25, lags
    settle()

    saved_limits, saved_timeouts, saved_runner = dict(runs.LIMITS_PER_HOUR), dict(runs.TIMEOUT_S), app.state.runner
    try:
        app.state.runner = runs.Runner(slots=1, queue=1)
        q = [ask(tok_ops, Q_OPS)[0] for _ in range(3)]
        assert [x.status_code for x in q] == [202, 202, 429] and q[2].headers.get("retry-after"), \
            [x.status_code for x in q]
        settle()
        runs.LIMITS_PER_HOUR["ask"] = 2
        app.state.runner = runs.Runner()
        lim = [ask(tok_ops, Q_OPS)[0] for _ in range(3)]
        assert [x.status_code for x in lim] == [202, 202, 429] and lim[2].json()["type"].endswith("rate_limited")
        settle()
        runs.TIMEOUT_S["ask"], FAKE.delay = 1, 2.5
        app.state.runner = runs.Runner()
        late, _ = ask(tok_ops, Q_OPS)
        ev_late = events_of(late.json()["events_url"], tok_ops)
        failed = [d for _, e, d in ev_late if e == "failed"]
        assert failed and failed[0]["status"] == 504 and "answer" not in [e for _, e, _ in ev_late], ev_late
        settle()

        runs.LIMITS_PER_HOUR["ask"], runs.TIMEOUT_S["ask"], FAKE.delay = 1000, 180, 3.0
        app.state.runner = runs.Runner()                # 4 slots + 20 queued
        convs = [client.post(f"{B}/conversations", headers=bearer(tok_ops)).json()["conversation_id"]
                 for _ in range(50)]
        burst = [ask(tok_ops, Q_OPS, conversation=c)[0] for c in convs]
        codes = [x.status_code for x in burst]
        assert codes.count(202) == 24 and codes.count(429) == 26 and 500 not in codes, codes
        assert all(x.headers.get("retry-after") for x in burst if x.status_code == 429)
        FAKE.delay = 0.0
        settle(120)
    finally:
        runs.LIMITS_PER_HOUR.clear()
        runs.LIMITS_PER_HOUR.update(saved_limits)
        runs.TIMEOUT_S.clear()
        runs.TIMEOUT_S.update(saved_timeouts)
        app.state.runner = saved_runner
        FAKE.delay = 0.0

    tok_fin = login(("employee", "Finance")).json()["token"]
    tok_ceo = login(("ceo", "Operations")).json()["token"]
    a_thread, a_run = acc.json()["thread_id"], acc.json()["run_url"]
    for url in (a_run, acc.json()["events_url"], f"{B}/questions/{a_thread}", f"{B}/conversations/{conv_ops}"):
        assert is_problem(client.get(url, headers=bearer(tok_fin)), 404), url
    other_q = client.post(f"{B}/conversations/{conv_ops}/questions", json={"question": Q_OPS},
                          headers=bearer(tok_fin))
    assert is_problem(other_q, 404)
    assert client.get(f"{B}/questions/{a_thread}", headers=bearer(tok_ceo)).status_code == 200
    assert client.get(f"{B}/conversations/{conv_ops}", headers=bearer(tok_ceo)).status_code == 200
    assert is_problem(client.post(f"{B}/conversations/{conv_ops}/questions", json={"question": Q_OPS},
                                  headers=bearer(tok_ceo)), 404)
    mine = {q["thread_id"] for q in client.get(f"{B}/questions", headers=bearer(tok_fin)).json()}
    assert a_thread not in mine
    stored = client.get(f"{B}/questions/{a_thread}", headers=bearer(tok_ops)).json()
    assert stored["status"] == "not_in_data" and stored["question"] == Q_OPS, stored
    turns = client.get(f"{B}/conversations/{conv_ops}", headers=bearer(tok_ops)).json()["turns"]
    assert [(t["turn_no"], t["status"], t["thread_id"]) for t in turns] == [(1, "not_in_data", a_thread)], turns
    # conversation memory (§6a, P6m): a follow-up resolved by code → `understood`; an ambiguous one asks back
    m1, conv_m1 = ask(tok_ops, "Where is vessel 36 now?")
    events_of(m1.json()["events_url"], tok_ops)
    m2, _ = ask(tok_ops, "When will it arrive?", conversation=conv_m1)
    ev_m2 = events_of(m2.json()["events_url"], tok_ops)
    und = next((d for _, e, d in ev_m2 if e == "understood"), None)
    assert und and und["by"] == "code" and und["used_entities"].get("vessel") == [36] and \
        "vessel 36" in und["standalone_question"], ev_m2
    c1, conv_c = ask(tok_ops, "Where are vessels 36 and 41 now?")
    events_of(c1.json()["events_url"], tok_ops)
    c2, _ = ask(tok_ops, "When will it arrive?", conversation=conv_c)
    ev_c2 = events_of(c2.json()["events_url"], tok_ops)
    ans_c2 = next(d for _, e, d in ev_c2 if e == "answer")
    assert ans_c2["status"] == "clarify" and ans_c2["model_calls"] == 0 and "36" in ans_c2["answer"] and \
        "41" in ans_c2["answer"] and "tool_called" not in [e for _, e, _ in ev_c2], ev_c2
    # the reply to the question asked back completes the pending question (2026-11-16), on a thread of its own
    c3, _ = ask(tok_ops, "vessel 41", conversation=conv_c)
    ev_c3 = events_of(c3.json()["events_url"], tok_ops)
    und3 = next((d for _, e, d in ev_c3 if e == "understood"), None)
    assert und3 and und3["by"] == "code" and und3["used_entities"].get("vessel") == [41] and \
        und3["standalone_question"].startswith("When will it arrive?") and "41" in und3["standalone_question"], ev_c3
    assert c3.json()["thread_id"] != c2.json()["thread_id"], (c2.json(), c3.json())
    with owner() as oc:
        rows_m = oc.execute("SELECT turn_no, resolved_by, standalone_question, frame, answer_masked, status FROM "
                            "api.conversation_turns WHERE conversation_id::text = ANY(%s) ORDER BY conversation_id, "
                            "turn_no", ([conv_m1, conv_c],)).fetchall()
    by_turn = [(r["resolved_by"], r["status"], r["frame"]) for r in rows_m]
    pending_c2 = {"clarify": {"kind": "vessel", "labels": {}, "options": [36, 41], "question": "When will it arrive?"}}
    assert ("code", "not_in_data", {"vessel": [36]}) in by_turn and ("clarify", "clarify", pending_c2) in by_turn, \
        by_turn
    assert all(r["answer_masked"] is None or "{" not in r["answer_masked"] for r in rows_m), rows_m
    DONE.append(5)
    print(f"✅ Phase 5 validation passed: POST 202 in {post_s * 1000:.0f} ms while the run takes 1.5 s (C7); one run "
          f"per conversation (409); a held thread lock → 409 (C5); queue full and the per-employee limit → 429 + "
          f"Retry-After (C8); time limit → failed 504; end order record → free → publish (D-F2); health/live ≤ {max(lags) * 1000:.0f} ms with 4 busy runs (C9); "
          f"50 at once → {codes.count(202)} accepted, {codes.count(429)} × 429, 0 × 500; another employee 404 on the "
          f"run / events / answer / conversation, the CEO reads but cannot continue; memory: a follow-up resolved by "
          f"code (`understood`), an ambiguous one asks back with 0 model calls, the turns' frames stored")

    # %% Phase 6 — uploads in a conversation
    FIX = ROOT / "Data" / "processed" / "rag" / "eval" / "uploads" / "fixtures"
    EXPECTED = json.loads((FIX.parent / "expected.json").read_text(encoding="utf-8"))

    def send(token, conv, name):
        with (FIX / name).open("rb") as f:
            return client.post(f"{B}/conversations/{conv}/uploads", headers=bearer(token),
                               files={"file": (name, f.read())})
    conv_up = client.post(f"{B}/conversations", headers=bearer(tok_ops)).json()["conversation_id"]
    ok = send(tok_ops, conv_up, "clean_D1.pdf")
    attack = send(tok_ops, conv_up, "inj_visible_en.pdf")
    shape = send(tok_ops, conv_up, "shape_missing_purpose.docx")
    text = send(tok_ops, conv_up, "shape_not_supported.txt")
    assert ok.status_code == 201 and ok.json()["accepted"] and ok.json()["chunks"] > 0, ok.text[:300]
    removed_where = [r["where"] for r in attack.json()["removed"]]       # "section 4.2 'Electrical check'"
    assert attack.status_code == 201 and len(removed_where) == len(EXPECTED["inj_visible_en.pdf"]["removed"]) and \
        all(w.startswith(f"section {n} ") for w, n in zip(removed_where, EXPECTED["inj_visible_en.pdf"]["removed"])), \
        attack.text[:300]
    for r, name in ((shape, "shape_missing_purpose.docx"), (text, "shape_not_supported.txt")):
        assert r.status_code == 422 and r.headers["content-type"].startswith("application/problem+json"), r.text[:200]
        # the fixture's own codes are all there (an uploader other than the fixture's may add its access refusal)
        assert set(EXPECTED[name]["codes"]) <= {x["code"] for x in r.json()["upload"]["reasons"]}, r.text[:300]
    listed = client.get(f"{B}/conversations/{conv_up}/uploads", headers=bearer(tok_ops)).json()
    accepted_ids = {ok.json()["document_id"], attack.json()["document_id"]}
    assert {u["document_id"] for u in listed} == accepted_ids, listed
    assert all("text" not in json.dumps(u) for u in listed)
    # the upload reaches the question as its own, untrusted list (the document tool through the run context)
    FAKE.call = ("search_documents", {"query": "reefer container pre-trip inspection electrical check", "k": 5})
    try:
        acc_up, _ = ask(tok_ops, "What does my uploaded procedure say about the reefer pre-trip inspection?",
                        conversation=conv_up)
        ev_up = events_of(acc_up.json()["events_url"], tok_ops)
    finally:
        FAKE.call = ("voyage_status", {"vessel_id": 234})
    called = [d["name"] for _, e, d in ev_up if e == "tool_called"]
    st_up = direct_graph.get_state({"configurable": {"thread_id": acc_up.json()["thread_id"]}}).values
    doc_ev = [r for r in (st_up.get("evidence") or {}).values() if r.get("tool") == "search_documents"]
    up_rows = [row for r in doc_ev for row in r.get("rows") or [] if row.get("lane") == "upload"]
    assert called == ["search_documents"] and doc_ev, (called, list((st_up.get("evidence") or {})))
    assert up_rows and all(row["trust"].startswith("untrusted_upload") for row in up_rows), up_rows[:1]
    assert "conversation uploads" in doc_ev[0]["source"]["name"], doc_ev[0]["source"]
    # owner-only: another employee gets 404, the CEO may read the list but not upload
    assert is_problem(send(tok_fin, conv_up, "clean_D1.pdf"), 404)
    assert is_problem(client.get(f"{B}/conversations/{conv_up}/uploads", headers=bearer(tok_fin)), 404)
    assert client.get(f"{B}/conversations/{conv_up}/uploads", headers=bearer(tok_ceo)).status_code == 200
    assert is_problem(send(tok_ceo, conv_up, "clean_D1.pdf"), 404)
    with app.state.runner.conversation(conv_up):          # an upload in progress keeps the conversation busy
        assert is_problem(ask(tok_ops, Q_OPS, conversation=conv_up)[0], 409)
    # promotion: an employee is refused; a manager's clean upload of their own department is filed for review
    assert is_problem(client.post(f"{B}/conversations/{conv_up}/uploads/{ok.json()['document_id']}/promotion",
                                  json={}, headers=bearer(tok_ops)), 403)
    tok_om = login(("manager", "Operations")).json()["token"]
    conv_m = client.post(f"{B}/conversations", headers=bearer(tok_om)).json()["conversation_id"]
    promotion_dir_existed = session_store.PROMOTION_DIR.exists()
    # two different Operations documents (D1 and the attack copy share NG-OPS-PRC-0042: the second would replace it)
    m_ok, m_bad = send(tok_om, conv_m, "clean_D4.docx"), send(tok_om, conv_m, "inj_visible_en.pdf")
    assert m_ok.status_code == 201 and m_ok.json()["document_id"] != m_bad.json()["document_id"], m_ok.text[:200]
    prom = client.post(f"{B}/conversations/{conv_m}/uploads/{m_ok.json()['document_id']}/promotion",
                       json={"note": "check"}, headers=bearer(tok_om))
    assert prom.status_code == 202 and prom.json()["status"] == "requested" and "folder" not in prom.json(), prom.text
    promoted_ids = [prom.json()["request_id"]]
    assert (session_store.PROMOTION_DIR / promoted_ids[0] / "request.json").exists()
    refused_prom = client.post(f"{B}/conversations/{conv_m}/uploads/{m_bad.json()['document_id']}/promotion",
                               json={}, headers=bearer(tok_om))
    assert is_problem(refused_prom, 422) and refused_prom.json()["problems"], refused_prom.text
    for rid_p in promoted_ids:                            # the check's request folder, removed again
        shutil.rmtree(session_store.PROMOTION_DIR / rid_p, ignore_errors=True)
    if not promotion_dir_existed and not any(session_store.PROMOTION_DIR.iterdir()):
        session_store.PROMOTION_DIR.rmdir()             # and the folder, when this check created it
    # remove one, then close: the uploads leave the memory
    gone = client.delete(f"{B}/conversations/{conv_up}/uploads/{ok.json()['document_id']}", headers=bearer(tok_ops))
    again = client.delete(f"{B}/conversations/{conv_up}/uploads/{ok.json()['document_id']}", headers=bearer(tok_ops))
    assert gone.status_code == 204 and is_problem(again, 404)
    assert client.delete(f"{B}/conversations/{conv_up}", headers=bearer(tok_ops)).status_code == 204
    assert client.get(f"{B}/conversations/{conv_up}/uploads", headers=bearer(tok_ops)).json() == []
    DONE.append(6)
    print(f"✅ Phase 6 validation passed: a clean upload accepted ({ok.json()['chunks']} chunks), an attack accepted "
          f"with {attack.json()['removed'][0]['where']} removed, two shapes refused as 422 problems with "
          f"their codes; the question's document tool returns {len(up_rows)} upload row(s) labelled untrusted_upload; "
          f"another employee 404, the CEO reads only; an upload holds the conversation busy (409); promotion: an "
          f"employee 403, a manager's clean upload filed ({len(promoted_ids)}), a screened one refused; delete and "
          f"close empty the memory")

    # %% Phase 7 — the weekly pack
    def _q(v, d):
        return Decimal(str(v)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)

    def m_sdr(v):
        return f"{_q(Decimal(str(v)) / 10 ** 6, 2):.2f}".replace("-", "−") + " M SDR"

    class PackScript:
        """Weekly_pack_check's good-mode script, shortened: one Insight tool round, notes, the sample slot draft."""
        week, ev = 5, None

        def __call__(self, role, msgs, tools, schema):
            w = self.week
            if schema is None:
                if any(x.type == "tool" for x in msgs):
                    return AIMessage(content="Findings ready.")
                return AIMessage(content="", tool_calls=[{"name": "finance_kpi", "args": {
                    "report_week": w, "dataset": "category"}, "id": f"cat_{w}"}])
            k, cats = self.ev["kpi.weekly"]["rows"][0], self.ev["kpi.category"]["rows"]
            if schema is gm.InsightNotes:
                return gm.InsightNotes(summary=[gm.Cited(text=f"Billed {m_sdr(k['billed_sdr'])} in week {w} of 2025",
                                                       evidence_ids=["kpi.weekly"])],
                                      drivers=[gm.Driver(vessel_category=c["vessel_category"], direction="up",
                                                        flagged_by_audit=False, explanation="largest change",
                                                        evidence_ids=["kpi.category"]) for c in cats[:3]],
                                      caveats=[])
            if schema is gm.SlidesDraft:                 # a revise re-drafts its related slides only
                return wp.slides_of(sample.slot_draft(w, self.ev), msgs)
            return gm.DeckDraft.model_validate(sample.slot_draft(w, self.ev))

    fm_user = ctx_mod.load_user(PEOPLE[("manager", "Finance")]["employee_id"])
    pack = PackScript()
    pack.ev = {**wp.kpi_evidence(fm_user, pack.week, "live"), **wp.audit_evidence(fm_user, pack.week, "live")}
    TMP_REPORTS = Path(tempfile.mkdtemp(prefix="api_check_reports_"))
    app.state.reports_dir, app.state.pack_prefix = TMP_REPORTS, "weekly_pack:apicheck:2025-W"
    pack_tid = f"weekly_pack:apicheck:2025-W{pack.week:02d}:1"
    THREADS.append(pack_tid)
    pg = wp.build_graph(roles.FakeRoles(pack), checkpointer.saver(), TMP_REPORTS)
    pcfg = {"configurable": {"thread_id": pack_tid}, "metadata": {"run_as": fm_user.employee_id}}
    for _ in pg.stream({"report_week": pack.week}, pcfg, context=ctx_mod.RunContext(fm_user), stream_mode="updates",
                       durability="sync"):
        pass
    tok_fm = login(("manager", "Finance")).json()["token"]
    listed_p = client.get(f"{B}/packs", headers=bearer(tok_fm)).json()
    assert [(x["thread_id"], x["state"]) for x in listed_p] == [(pack_tid, "pending")], listed_p
    shown = client.get(f"{B}/packs/{pack_tid}", headers=bearer(tok_fm)).json()
    assert shown["decisions"] and shown["has_preview"] and shown["draft"]["bullets"], shown.keys()
    # Frontend plan F0: what the approver may still do, and the series the deck's charts draw (render.build_spec)
    assert shown["allowed"]["decide"] and shown["allowed"]["revise_left"] == wp.MAX_REVISES and         shown["allowed"]["addition_slides"] == list(wp.v2.ADDITION_SLIDES), shown["allowed"]
    assert shown["charts_drawn"] and all(c["series"] and c["categories"] for cs in shown["charts_drawn"].values()
                                         for c in cs), shown["charts_drawn"]
    pv = client.get(f"{B}/packs/{pack_tid}/preview", headers=bearer(tok_fm))
    assert pv.status_code == 200 and pv.headers["content-type"].startswith("application/vnd.openxml") and \
        pv.content[:2] == b"PK", (pv.status_code, pv.headers.get("content-type"))
    for url in (f"{B}/packs", f"{B}/packs/{pack_tid}"):
        assert is_problem(client.get(url, headers=bearer(tok_ops)), 403), url
    assert is_problem(client.get(f"{B}/packs/weekly_pack:live:2025-W01:1", headers=bearer(tok_fm)), 404)
    def review_version():
        return client.get(f"{B}/packs/{pack_tid}", headers=bearer(tok_fm)).json()["draft_sha"]

    no = client.post(f"{B}/packs/{pack_tid}/decision", json={"decision": "approve", "draft_sha": review_version()},
                     headers=bearer(tok_fin))
    assert is_problem(no, 403), no.text
    billed_idx = next(i for i, b in enumerate(shown["draft"]["bullets"]) if b["text"].startswith("Billed"))
    edit = client.post(f"{B}/packs/{pack_tid}/decision", headers=bearer(tok_fm), json={
        "draft_sha": review_version(),
        "decision": "edit", "comment": "check", "edits": [{"bullet": billed_idx, "text":
            f"Billing was {m_sdr(pack.ev['kpi.weekly']['rows'][0]['billed_sdr'])} in week {pack.week} of 2025"}]})
    ev_edit = events_of(edit.json()["events_url"], tok_fm)
    assert edit.status_code == 202 and "approval_needed" in [e for _, e, _ in ev_edit], ev_edit
    # approver-additions plan Phase E: chart variants + an addition (an edit), the wrong mixes as 422, a revise (the
    # Writer drafts again: the pack's own scripted models for this decision), every change seen through GET
    dec_url, pack_url = f"{B}/packs/{pack_tid}/decision", f"{B}/packs/{pack_tid}"
    app.state.roles_factory = lambda: roles.FakeRoles(pack)
    ch = client.post(dec_url, headers=bearer(tok_fm), json={
        "draft_sha": review_version(),
        "decision": "edit", "charts": [{"chart": "variance", "rows": "top5"}],
        "additions": [{"slide": 6, "text": "Finance will follow these receivables this week."}]})
    ev_ch = events_of(ch.json()["events_url"], tok_fm)
    shown_ch = client.get(pack_url, headers=bearer(tok_fm)).json()
    assert ch.status_code == 202 and "approval_needed" in [e for _, e, _ in ev_ch], ev_ch
    assert shown_ch["charts"]["variance"]["rows"] == "top5" and \
        sum(b.get("origin") == "approver" for b in shown_ch["draft"]["bullets"]) == 1, shown_ch["charts"]
    wrong = [client.post(dec_url, json={**j, "draft_sha": review_version()}, headers=bearer(tok_fm)) for j in (
        {"decision": "revise", "steer": "Look at receivables.", "edits": [{"bullet": 0, "text": "y"}]},
        {"decision": "edit"}, {"decision": "edit", "charts": [{"chart": "aging"}]},
        {"decision": "revise", "analysis_edits": [{"target": "summary", "op": "add", "text": "x"}]})]
    assert all(is_problem(r, 422) for r in wrong), [r.status_code for r in wrong]
    caveat = "The approver asked for a second look at receivables."
    rv = client.post(dec_url, headers=bearer(tok_fm), json={
        "draft_sha": review_version(),
        "decision": "revise", "analysis_edits": [{"target": "caveat", "op": "add", "text": caveat}]})
    ev_rv = events_of(rv.json()["events_url"], tok_fm)
    rv_nodes = [d["name"] for _, e, d in ev_rv if e == "node" and d["phase"] == "start"]
    shown_rv = client.get(pack_url, headers=bearer(tok_fm)).json()
    assert rv.status_code == 202 and "writer" in rv_nodes and "approval_needed" in [e for _, e, _ in ev_rv], rv_nodes
    # targeted-revise plan: a caveat re-drafts slide 2 only; the chart variant and the slide-6 addition stay
    assert shown_rv["redrafted"] and shown_rv["redrafted_slides"] == [2] and shown_rv["charts"]["variance"]["rows"] == "top5" \
        and shown_rv["insight"]["caveats"] == [caveat] and \
        [b["slide"] for b in shown_rv["draft"]["bullets"] if b.get("origin") == "approver"] == [6], \
        (shown_rv["redrafted_slides"], shown_rv["charts"])
    # approver-request plan Phase B: the manager's request in words → a proposal (one fake call, nothing applied) →
    # confirmed → applied and waiting again; a Finance employee 403; a changed draft 409; a wrong step 422

    class RequestFake:
        def __call__(self, role, msgs, tools, schema):
            if schema is ar_mod.ApproverRequest:
                w = 8 if "8 weeks" in str(msgs[-1].content) else 4
                return {"action": "change", "understood": f"the trend over {w} weeks",
                        "charts": [{"chart": "trend", "weeks": w}]}
            return pack(role, msgs, tools, schema)

    app.state.roles_factory = lambda: roles.FakeRoles(RequestFake())
    req_url = f"{B}/packs/{pack_tid}/request"
    too_long = client.post(req_url, json={"request": "show the trend over 8 weeks"}, headers=bearer(tok_fm))
    ans_tl = next(d for _, e, d in events_of(too_long.json()["events_url"], tok_fm) if e == "answer")
    assert ans_tl["status"] == "ask_back" and "week 8 or later" in ans_tl["answer"]["ask_back"] and \
        ans_tl["answer"]["steps"] == [], ans_tl        # week 5: the window rule said before any confirm
    rq = client.post(req_url, json={"request": "show the billing trend over 4 weeks"}, headers=bearer(tok_fm))
    ans_rq = next(d for _, e, d in events_of(rq.json()["events_url"], tok_fm) if e == "answer")
    prop = ans_rq["answer"]
    assert rq.status_code == 202 and ans_rq["status"] == "proposed" and ans_rq["model_calls"] == 1 and \
        prop["steps"] == [{"decision": "edit", "edits": [], "additions": [],
                           "charts": [{"chart": "trend", "weeks": 4}]}], ans_rq
    # the edit's variance variant survives the revise (targeted-revise plan T2); the trend is still the default
    assert client.get(pack_url, headers=bearer(tok_fm)).json()["charts"] == shown_rv["charts"], \
        "a proposal changed the pack"
    assert is_problem(client.post(req_url, json={"request": "show 8 weeks"}, headers=bearer(tok_fin)), 403)
    assert is_problem(client.post(req_url, json={"request": "x"}, headers=bearer(tok_fm)), 422)
    conf_url, conf_prop = f"{req_url}/confirm", {k: prop[k] for k in ("understood", "steps", "draft_sha",
                                                                     "reread_text")}
    stale = client.post(conf_url, headers=bearer(tok_fm), json={"request": "show 8 weeks", "proposal": {
        **conf_prop, "draft_sha": "0" * 16}})
    assert is_problem(stale, 409), stale.text
    assert is_problem(client.post(conf_url, headers=bearer(tok_fm), json={"request": "show 8 weeks", "proposal": {
        **conf_prop, "steps": [{"decision": "edit"}]}}), 422)
    cf = client.post(conf_url, json={"request": "show the billing trend over 4 weeks", "proposal": conf_prop},
                     headers=bearer(tok_fm))
    ev_cf = events_of(cf.json()["events_url"], tok_fm)
    ans_cf = next(d for _, e, d in ev_cf if e == "answer")
    shown_cf = client.get(pack_url, headers=bearer(tok_fm)).json()
    assert cf.status_code == 202 and "approval_needed" in [e for _, e, _ in ev_cf] and \
        ans_cf["answer"]["outcomes"] == [{"decision": "edit", "outcome": "edited"}], ans_cf
    assert shown_cf["charts"]["trend"]["weeks"] == 4 and shown_cf["approval_log"][-1]["comment"] == \
        "request: show the billing trend over 4 weeks", shown_cf["approval_log"][-1]
    app.state.roles_factory = lambda: roles.FakeRoles(FAKE)
    appr = client.post(f"{B}/packs/{pack_tid}/decision", json={"decision": "approve", "draft_sha": review_version()},
                       headers=bearer(tok_fm))
    ev_appr = events_of(appr.json()["events_url"], tok_fm)
    done_status = next(d for _, e, d in ev_appr if e == "answer")["status"]
    assert done_status == "published", ev_appr
    dk = client.get(f"{B}/packs/{pack_tid}/deck", headers=bearer(tok_fm))
    assert dk.status_code == 200 and dk.content[:2] == b"PK" and len(dk.content) > 20_000, dk.status_code
    again_d = client.post(f"{B}/packs/{pack_tid}/decision", json={"decision": "approve", "draft_sha": review_version()},
                          headers=bearer(tok_fm))
    assert is_problem(again_d, 409), again_d.text
    meta_run_as = {dict(h.metadata or {}).get("run_as") for h in pg.get_state_history(pcfg)} - {None}
    assert meta_run_as == {fm_user.employee_id}, meta_run_as
    # approver-request plan §2c: the dashboard's "this week's pack" — the approved summary and the manager's trend
    # (4 weeks) drawn from the finance rows as the asker; the other chart its default; 403 / 404 / 422
    wk = client.get(f"{B}/finance/pack", params={"week": pack.week}, headers=bearer(tok_fm))
    wkj = wk.json()
    assert wk.status_code == 200 and wkj["thread_id"] == pack_tid and wkj["summary"] and \
        wkj["approver_employee_id"] == fm_user.employee_id, wk.text[:300]
    assert [c["choice"]["kind"] for c in wkj["charts"]] == ["trend", "category"] and \
        wkj["charts"][0]["choice"]["weeks"] == 4 and len(wkj["charts"][0]["categories"]) == 4, \
        [c["choice"] for c in wkj["charts"]]
    assert is_problem(client.get(f"{B}/finance/pack", params={"week": pack.week}, headers=bearer(tok_ops)), 403)
    assert is_problem(client.get(f"{B}/finance/pack", params={"week": pack.week + 1}, headers=bearer(tok_fm)), 404)
    assert is_problem(client.get(f"{B}/finance/pack", params={"week": 60}, headers=bearer(tok_fm)), 422)
    shutil.rmtree(TMP_REPORTS, ignore_errors=True)
    DONE.append(7)
    print(f"✅ Phase 7 validation passed: a test pack (prefix weekly_pack:apicheck, temp reports) listed / shown / "
          f"previewed for the Finance manager, 403 for an operations employee, 404 outside the prefix; a Finance "
          f"employee's decision 403; edit → re-validated + approval_needed; approve → published, the deck downloads "
          f"({len(dk.content) // 1024} KB); a second decision 409; the run identity unchanged")

    # %% Phase 8 — route advice + the watch
    ra_acc = client.post(f"{B}/route-advice", headers=bearer(tok_ops),
                         json={"vessel_id": 36, "origin": "SGSIN", "destination": "JPTYO"})
    assert ra_acc.status_code == 202, ra_acc.text
    THREADS.append(ra_acc.json()["thread_id"])
    ev_ra = events_of(ra_acc.json()["events_url"], tok_ops)
    ra_ans = next(d for _, e, d in ev_ra if e == "answer")
    assert ra_ans["status"] == "no_suez_on_route" and ra_ans["model_calls"] == 0, ra_ans
    ra_tid = ra_acc.json()["thread_id"]
    assert ra_tid in {x["thread_id"] for x in client.get(f"{B}/route-advice", headers=bearer(tok_ops)).json()}
    assert client.get(f"{B}/route-advice/{ra_tid}", headers=bearer(tok_ops)).json()["status"] == "no_suez_on_route"
    assert is_problem(client.get(f"{B}/route-advice/{ra_tid}", headers=bearer(tok_fin)), 404)
    assert client.get(f"{B}/route-advice/{ra_tid}", headers=bearer(tok_ceo)).status_code == 200
    bad = client.post(f"{B}/route-advice", headers=bearer(tok_ops),
                      json={"vessel_id": 36, "origin": "SGSIN", "destination": "JPTYO", "run_as": 1})
    assert is_problem(bad, 422), bad.text
    for tok in (tok_ops, tok_fin):
        al = client.get(f"{B}/voyage-watch/alerts", headers=bearer(tok)).json()
        assert al["status"] == "ok" and al["thread_id"].startswith("voyage_watch:"), al.get("status")
    wruns = client.get(f"{B}/voyage-watch/runs", headers=bearer(tok_fin)).json()
    wrun = client.get(f"{B}/voyage-watch/runs/{wruns[-1]['thread_id']}", headers=bearer(tok_fin)).json()
    assert wruns and wrun["status"], wrun
    assert all({"vessel_id", "eta_utc", "eta_in_h"} <= set(e) for e in wrun["etas"]), wrun["etas"][:1]
    assert is_problem(client.get(f"{B}/voyage-watch/runs/not-a-watch", headers=bearer(tok_fin)), 404)
    DONE.append(8)
    print(f"✅ Phase 8 validation passed: route advice SGSIN → JPTYO through the run executor = no_suez_on_route with 0 "
          f"model calls; the stored advice for its asker and the CEO, 404 for another employee; an unknown field 422; "
          f"the saved watch alerts ({al['thread_id']}) and {len(wruns)} watch runs readable by every employee "
          f"(the identity checked), the run's ETA table ({len(wrun['etas'])} vessels)")

    # %% Phase 9 — security headers, CORS, limits
    for r in (client.get(f"{B}/health/live"), unknown, r404, r500, r413):
        assert headers_ok(r), dict(r.headers)
    assert client.get(f"{B}/health/live").headers["content-security-policy"] == middleware.JSON_CSP
    docs = client.get("/docs")
    assert docs.status_code == 200 and docs.headers["content-security-policy"] == middleware.DOCS_CSP
    mine = str(uuid.uuid4())
    assert client.get(f"{B}/health/live", headers={"X-Request-ID": mine}).headers["x-request-id"] == mine
    other = client.get(f"{B}/health/live", headers={"X-Request-ID": "<script>"}).headers["x-request-id"]
    assert other != "<script>" and uuid.UUID(other)
    origin = config.cors_origins()[0]
    pre = client.options(f"{B}/me", headers={"Origin": origin, "Access-Control-Request-Method": "GET",
                                             "Access-Control-Request-Headers": "authorization"})
    evil = client.options(f"{B}/me", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    simple = client.get(f"{B}/health/live", headers={"Origin": "http://evil.example"})
    assert pre.status_code == 200 and pre.headers.get("access-control-allow-origin") == origin, dict(pre.headers)
    assert "access-control-allow-credentials" not in pre.headers
    assert "access-control-allow-origin" not in evil.headers and "access-control-allow-origin" not in simple.headers
    saved = os.environ.get("API_CORS_ORIGINS")
    os.environ["API_CORS_ORIGINS"] = "*"
    try:
        config.cors_origins()
        raise AssertionError("'*' accepted as a CORS origin")
    except ValueError:
        pass
    finally:
        if saved is None:
            os.environ.pop("API_CORS_ORIGINS", None)
        else:
            os.environ["API_CORS_ORIGINS"] = saved
    # the access log: one line per request, the route as its template, no token / password / question / body
    raw_log = ACCESS_LOG.read_text(encoding="utf-8")
    log_rows = [json.loads(x) for x in raw_log.splitlines()]
    assert len(log_rows) > 200 and all(set(x) == {"at", "method", "route", "status", "ms", "employee_id",
                                                  "request_id"} for x in log_rows), log_rows[:1]
    assert any(x["route"].endswith("/runs/{run_id}/events") for x in log_rows) and \
        not any(acc.json()["run_id"] in x["route"] for x in log_rows), "routes logged as templates"
    assert not any(t in raw_log for t in (tok, tok_ops, PEOPLE[FM]["password"], Q_OPS, pw)), "a secret or a question"
    assert {x["status"] for x in log_rows} >= {200, 202, 401, 404, 413, 422, 429, 500}
    DONE.append(9)
    print(f"✅ Phase 9 validation passed: security headers on 200 / 401 / 404 / 413 / 500; request id echoed when a "
          f"UUID, replaced otherwise; the docs' own CSP; CORS for {origin} only, no credentials; '*' refused; the "
          f"access log {len(log_rows)} lines, templates only, no token / password / question")

    # %% Phase 10 — the chart catalogue and the smart view (approver-additions plan Phase F)
    from pipelines.agents.tools import finance as fin_tool

    class ViewFake:
        """The views' one structured call: a question naming week 23 → a category view; none → no week (ask back)."""

        def __call__(self, role, msgs, tools, schema):
            assert schema is gm.ViewChoice and role == "tools", (role, schema)
            if "week 23" in str(msgs[-1].content):
                return gm.ViewChoice(kind="category", week=23, measure="budget_variance_pct", rows="top5")
            return {"kind": "trend", "week": None, "series": ["ar_sdr"]}

    cat = client.get(f"{B}/charts/catalogue", headers=bearer(tok_ops)).json()
    assert set(cat) == {"pack", "views"} and cat["pack"]["charts"] == ["trend", "variance"], cat.keys()
    choice = {"kind": "category", "week": 23, "measure": "budget_variance_pct", "rows": "top5", "compare_week": 22}
    vr = client.post(f"{B}/views", json={"choice": choice}, headers=bearer(tok_fm))
    spec = vr.json()
    rows23 = {r["vessel_category"]: r for r in fin_tool.finance_kpi(fm_user, report_week=23, dataset="category").rows}
    rows22 = {r["vessel_category"]: r for r in fin_tool.finance_kpi(fm_user, report_week=22, dataset="category").rows}
    top5 = sorted(rows23.values(), key=lambda r: (r["budget_variance_pct"] or 0, r["vessel_category"]))[-5:]
    assert vr.status_code == 200 and spec["categories"] == [r["vessel_category"] for r in top5], spec
    assert [s["values"] for s in spec["series"]] == [[r["budget_variance_pct"] for r in top5],
                                                    [rows22[r["vessel_category"]]["budget_variance_pct"] for r in top5]]
    tr = client.post(f"{B}/views", json={"choice": {"kind": "trend", "week": 30, "weeks": 26}},
                     headers=bearer(tok_fm)).json()
    assert len(tr["categories"]) == 26 and tr["categories"][-1].endswith("30") and len(tr["sources"]) == 2, tr
    assert is_problem(client.post(f"{B}/views", json={"choice": choice}, headers=bearer(tok_ops)), 403)
    assert is_problem(client.post(f"{B}/views", json={"choice": {"kind": "trend"}}, headers=bearer(tok_fm)), 422)
    assert is_problem(client.post(f"{B}/views", json={"choice": {"kind": "aging", "week": 5, "measure": "x"}},
                                  headers=bearer(tok_fm)), 422)
    assert is_problem(client.post(f"{B}/views", json={"choice": choice, "question": "both"},
                                  headers=bearer(tok_fm)), 422)
    app.state.roles_factory = lambda: roles.FakeRoles(ViewFake())
    q1 = client.post(f"{B}/views", json={"question": "Billed vs budget % by category for week 23, top 5"},
                     headers=bearer(tok_fm))
    a1 = next(d for _, e, d in events_of(q1.json()["events_url"], tok_fm) if e == "answer")
    q2 = client.post(f"{B}/views", json={"question": "Show the receivables trend"}, headers=bearer(tok_fm))
    a2 = next(d for _, e, d in events_of(q2.json()["events_url"], tok_fm) if e == "answer")
    app.state.roles_factory = lambda: roles.FakeRoles(FAKE)
    assert q1.status_code == 202 and a1["status"] == "answered" and a1["model_calls"] == 1 and \
        a1["view"]["categories"] == [r["vessel_category"] for r in top5], a1
    assert a2["status"] == "ask_back" and a2["view"] is None and "week" in a2["answer"], a2
    assert is_problem(client.post(f"{B}/views", json={"question": "Billed by category week 23"},
                                  headers=bearer(tok_ops)), 403)
    DONE.append(10)
    print("✅ Phase 10 validation passed: the catalogue for every employee; a view by choice = finance_kpi (top 5 of week "
          "23 vs week 22, a 26-week trend from two results); 403 outside Finance, 422 for no week / an option of "
          "another view / both inputs; a question → one model call → the same view; no week → ask back")

    # %% Phase 11 — the frontend contract (Frontend plan F0 / F0b / D-FE-1)
    from pipelines.api import fake as fake_mod
    from pipelines.api import schemas as sch
    sys.path.insert(0, str(ROOT / "tools"))
    import export_approval_cases                                    # noqa: E402

    app.openapi_schema = None                       # Phase 3 added test-only routes (/_check/*): the app's own schema
    spec_all = app.openapi()
    spec_all = {**spec_all, "paths": {k: v for k, v in spec_all["paths"].items() if "/_check/" not in k}}
    assert spec_all["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    open_routes = sorted(f"{m.upper()} {p}" for p, v in spec_all["paths"].items() for m, op in v.items()
                         if not op.get("security"))
    assert open_routes == ["GET /api/v1/health/live", "POST /api/v1/auth/login"], open_routes
    untyped = [f"{m} {p}" for p, v in spec_all["paths"].items() for m, op in v.items()
               for c, r in op["responses"].items() if c < "300"
               and (sc := (r.get("content") or {}).get("application/json", {}).get("schema")) is not None
               and "$ref" not in sc and "$ref" not in (sc.get("items") or {})]
    assert untyped == [], untyped
    # F0b: the finance pages' reads = the tools' rows, under the tools' RBAC
    wk = client.get(f"{B}/finance/weeks", headers=bearer(tok_fm))
    assert wk.status_code == 200 and wk.json()[0]["report_week"] == 1 and len(wk.json()) >= 23, wk.text[:200]
    fw = client.get(f"{B}/finance/weekly", params={"week": 23}, headers=bearer(tok_fm)).json()
    tool_w = fin_tool.finance_kpi(fm_user, report_week=23, dataset="weekly")
    assert fw["dataset"] == "weekly" and fw["rows"][0]["billed_sdr"] == tool_w.rows[0]["billed_sdr"] and         fw["source"]["name"] == "finance.kpi_weekly", fw.get("source")
    od = client.get(f"{B}/finance/overdue", params={"week": 23, "limit": 50}, headers=bearer(tok_fm)).json()
    assert od["status"] == "ok" and len(od["rows"]) == len(fin_tool.finance_kpi(fm_user, report_week=23,
                                                                                 dataset="overdue", limit=50).rows)
    from pipelines.agents.tools import audit as audit_tool
    au = client.get(f"{B}/finance/invoice-audit", params={"week": 23}, headers=bearer(tok_fm)).json()
    assert au["invoices_checked"] == audit_tool.invoice_audit(fm_user, report_week=23).invoices_checked, au.keys()
    # web dashboards plan (migration 029, D-WD-2…4): the breakdown = the view's rows; the export = a workbook whose
    # sheets hold the same rows, refused outside the finance_kpi rule
    bd = client.get(f"{B}/finance/breakdown", params={"week": 23, "dimension": "priced_condition"},
                    headers=bearer(tok_fm)).json()
    assert bd["source"]["name"] == "finance.kpi_weekly_breakdown" and \
        round(sum(r["billed_sdr"] for r in bd["rows"]), 2) == tool_w.rows[0]["billed_sdr"], bd
    xl = client.get(f"{B}/finance/export", params={"week": 23, "page": "revenue"}, headers=bearer(tok_fm))
    from openpyxl import load_workbook
    import io as _io
    wb_ = load_workbook(_io.BytesIO(xl.content))
    assert xl.status_code == 200 and wb_.sheetnames[0] == "About" and "Laden vs ballast" in wb_.sheetnames, \
        wb_.sheetnames
    # amendment 1 (D-WD-6): one figure = its own rows (+ the compare week's), as one sheet + About or as CSV
    fx = client.get(f"{B}/finance/export/figure", params={"week": 23, "figure": "breakdown",
                                                          "dimension": "priced_condition", "compare": 22},
                    headers=bearer(tok_fm))
    wbf = load_workbook(_io.BytesIO(fx.content))
    assert fx.status_code == 200 and wbf.sheetnames == ["About", "Laden vs ballast"] and \
        wbf["Laden vs ballast"].max_row - 1 == 2 * len(bd["rows"]), wbf.sheetnames
    fc = client.get(f"{B}/finance/export/figure", params={"week": 23, "figure": "category", "format": "csv"},
                    headers=bearer(tok_fm))
    lines = fc.content.decode("utf-8-sig").splitlines()
    assert fc.status_code == 200 and lines[0].endswith("source_view,source_filter") and \
        len(lines) - 1 == len(fin_tool.finance_kpi(fm_user, report_week=23, dataset="category").rows), lines[:2]
    assert is_problem(client.get(f"{B}/finance/export/figure", params={"week": 23, "figure": "breakdown"},
                                 headers=bearer(tok_fm)), 422)
    for url in (f"{B}/finance/weeks", f"{B}/finance/weekly?week=23", f"{B}/finance/invoice-audit?week=23",
                f"{B}/finance/breakdown?week=23&dimension=route", f"{B}/finance/export?week=23&page=overview",
                f"{B}/finance/export/figure?week=23&figure=trend"):
        assert is_problem(client.get(url, headers=bearer(tok_ops)), 403), url
    assert is_problem(client.get(f"{B}/finance/nope?week=23", headers=bearer(tok_fm)), 422)
    assert is_problem(client.get(f"{B}/finance/weekly?week=60", headers=bearer(tok_fm)), 422)
    # D-FE-1: the answer carries where each bound number sits; every span's text is the rendered text at its offsets
    app.state.roles_factory = lambda: roles.FakeRoles(fake_mod.WebFake())
    qa, _ = ask(tok_fm, "How much did PortPilot bill in week 23 of 2025?")
    ans = next(d for _, e, d in events_of(qa.json()["events_url"], tok_fm) if e == "answer")
    qo, _ = ask(tok_ops, "How much did PortPilot bill in week 23 of 2025?")
    evo = events_of(qo.json()["events_url"], tok_ops)
    app.state.roles_factory = lambda: roles.FakeRoles(FAKE)
    u16 = ans["answer"].encode("utf-16-le")
    assert ans["status"] == "answered" and len(ans["numbers"]) == 3, ans
    for sp in ans["numbers"]:
        assert u16[2 * sp["start"]:2 * sp["end"]].decode("utf-16-le") == sp["text"], sp
        assert sp["evidence_id"] == "insight.web" and sp["source"] == "finance.kpi_weekly" and             sp["filter"] == "report_week = 23", sp
    assert ans["numbers"][0]["field"] == "billed_sdr" and ans["evidence"]["insight.web"]["tool"] == "finance_kpi"
    ans_o = next(d for _, e, d in evo if e == "answer")
    assert any(e == "tool_refused" for _, e, _ in evo) and ans_o["numbers"] == [], ans_o
    # every stored event and result validates against the typed union the browser reads
    run_o = client.get(qa.json()["run_url"], headers=bearer(tok_fm)).json()
    for ev_ in run_o["events"]:
        sch.RUN_EVENT.validate_python(ev_)
    assert sch.AnswerData.model_validate(run_o["result"]).numbers, run_o["result"]
    # the approval rule cases the web tests against = the API's request model today
    fixture = ROOT / "web" / "tests" / "fixtures" / "approval_cases.json"
    assert fixture.read_text(encoding="utf-8") == export_approval_cases.build(), "run tools/export_approval_cases.py"
    DONE.append(11)
    print(f"✅ Phase 11 validation passed: OpenAPI with the bearer scheme on every route but sign-in and health/live, "
          f"no untyped 200; /finance/* = finance_kpi / invoice_audit rows (weeks {len(wk.json())}, overdue "
          f"{len(od['rows'])}, audit {au['invoices_checked']} invoices), 403 outside Finance, 422 for a bad dataset / "
          f"week; an answer's {len(ans['numbers'])} number spans sit exactly at their offsets; a refused asker gets "
          f"none; every event validates against the RunEvent union; the approval cases match DecisionIn")
finally:
    settle()
    client.__exit__(None, None, None)
    n_logins, n_audit, n_threads = cleanup()
    print(f"clean-up: {n_logins} throw-away login(s), {n_audit} audit row(s), {n_threads} thread(s) of this run "
          "deleted")


# %% Final Checkpoint
PHASES = {0: "skeleton", 1: "auth", 2: "RBAC / IDOR matrix", 3: "error mapping", 4: "event contract", 5: "ask",
          6: "uploads", 7: "weekly pack", 8: "route advice + watch alerts", 9: "security headers, CORS, limits",
          10: "chart catalogue + smart view", 11: "frontend contract (F0)"}
pending = [f"{k} {v}" for k, v in PHASES.items() if k not in DONE]
assert DONE == sorted(DONE) and set(DONE) <= set(PHASES)
print(f"Final Checkpoint: done {DONE}; pending: {pending}")
print(f"✅ Final Checkpoint: {len(DONE)} / {len(PHASES)} phases passed")
