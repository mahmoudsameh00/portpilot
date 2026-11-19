"""The API's real smoke (FastAPI plan §10, P7): the real server (`Serve.py`, its own process, the real models over
llm.py's shared quota) driven over HTTP the way the frontend will — sign-in, a question streamed over SSE (fetch-style,
with the bearer token), the answer read back.

Plan:    dev/history/archive/2026-11-05_FastAPI_plan.md (approved 2026-11-03).
Run:     $env:API_SMOKE = '1'; uv run python dev/tools/run.py dev/checks/api/Api_smoke.py
         without API_SMOKE=1 nothing is called (the script says so and ends).
Reads:   .env; the databases; the real models (≈ 10–15 flash-lite requests: one English and one Egyptian Arabic finance
         question, an upload question, one route advice with its writer call).
Writes:  throw-away logins for two employees without one (owner account) and what the server writes for them — their
         `ask:` / `route_advice:` threads, conversations, audit rows — all deleted at the end; the server's lines in
         reports/_log/api.jsonl stay (the real access log). Model replies in the llm cache, as every real run.
Re-run:  safe; a re-run answers from the llm cache (0 new calls).

Phases
1. Start: the server answers `health/live` on its port; sign-in → a token; `health/ready` every store up.
2. A Finance employee asks in English and in Egyptian Arabic about week 23's billing → `answered`, a figure bound to
   `finance_kpi`, the stream in contract order.
3. An Operations employee uploads `clean_D1.pdf` and asks about it → the answer's evidence includes the upload rows.
4. Route advice SGSIN → NLRTM for vessel 36 → a recommendation (one writer call) through the run executor.
5. The weekly pack: there is no pending live pack today (the next one is made on Monday): reported, not decided.
Final Checkpoint.
"""
# %% Setup
import json
import os
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import psycopg
from psycopg.rows import dict_row

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from pipelines.agents import checkpointer, scheduling  # noqa: E402
from pipelines.agents.graphs import weekly_pack  # noqa: E402
from pipelines.api import passwords  # noqa: E402
from pipelines.lib.common import load_env  # noqa: E402

load_env(ROOT)
if os.environ.get("API_SMOKE") != "1":
    print("API_SMOKE is not 1: the real smoke calls the real models; set it to run (nothing was called)")
    raise SystemExit(0)
E = os.environ
PORT = 8766
BASE = f"http://127.0.0.1:{PORT}/api/v1"
DONE: list[int] = []
started_at = datetime.now(timezone.utc)
THREADS: list[str] = []


def owner():
    return psycopg.connect(host=E["PGHOST"], port=E["PGPORT"], dbname=E["PGDATABASE"], user=E["PGUSER"],
                           password=E["PGPASSWORD"], autocommit=True, row_factory=dict_row)


with owner() as oc:
    free = oc.execute("SELECT e.employee_id, e.email, r.role_name AS role, d.department_name AS dept FROM employees e "
                      "JOIN roles r USING (role_id) JOIN departments d USING (department_id) WHERE e.employee_id NOT "
                      "IN (SELECT employee_id FROM api.logins) AND r.role_name = 'employee' ORDER BY 1").fetchall()
    who = {d: next({**r, "password": secrets.token_urlsafe(16)} for r in free if r["dept"] == d)
           for d in ("Finance", "Operations")}
    for w in who.values():
        oc.execute("INSERT INTO api.logins (employee_id, password_hash) VALUES (%s, %s)",
                   (w["employee_id"], passwords.hash_password(w["password"])))
IDS = [w["employee_id"] for w in who.values()]
server = subprocess.Popen([sys.executable, str(ROOT / "pipelines" / "scripts" / "api" / "Serve.py"), "--port",
                           str(PORT)], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
http = httpx.Client(timeout=30)


def stream(url: str, token: str) -> list[tuple[str, dict]]:
    out, cur = [], {}
    with http.stream("GET", url, headers={"Authorization": f"Bearer {token}"}, timeout=300) as s:
        for line in s.iter_lines():
            if line.startswith("event:"):
                cur["event"] = line[6:].strip()
            elif line.startswith("data:"):
                cur["data"] = json.loads(line[5:].strip())
            elif not line and cur:
                out.append((cur["event"], cur["data"]))
                cur = {}
    return out


def ask(token: str, question: str, conv: str | None = None) -> tuple[dict, list]:
    h = {"Authorization": f"Bearer {token}"}
    conv = conv or http.post(f"{BASE}/conversations", headers=h).json()["conversation_id"]
    acc = http.post(f"{BASE}/conversations/{conv}/questions", json={"question": question}, headers=h)
    assert acc.status_code == 202, acc.text
    THREADS.append(acc.json()["thread_id"])
    ev = stream(f"http://127.0.0.1:{PORT}{acc.json()['events_url']}", token)
    return next(d for e, d in ev if e == "answer"), ev


try:
    # %% Phase 1 — the server
    for _ in range(120):
        try:
            if http.get(f"{BASE}/health/live", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.5)
    tok = {d: http.post(f"{BASE}/auth/login", json={"email": w["email"], "password": w["password"]}).json()["token"]
           for d, w in who.items()}
    ready = http.get(f"{BASE}/health/ready", headers={"Authorization": f"Bearer {tok['Finance']}"}).json()
    assert ready["status"] == "ready", ready
    DONE.append(1)
    print(f"✅ Phase 1 validation passed: the server on 127.0.0.1:{PORT}; two sign-ins; ready "
          f"{sum(c['ok'] for c in ready['components'])} / {len(ready['components'])}")

    # %% Phase 2 — finance questions, English and Egyptian Arabic
    answers = {}
    for lang, q in (("en", "How much did we bill in week 23 of 2025?"), ("ar", "كام فوترنا في الأسبوع 23 من 2025؟")):
        a, ev = ask(tok["Finance"], q)
        names = [e for e, _ in ev]
        assert names[:2] == ["queued", "started"] and names[-2:] == ["answer", "done"], names
        assert a["status"] == "answered" and any(v["tool"] == "finance_kpi" for v in a["evidence"].values()), a
        answers[lang] = a
        print(f"  {lang}: {a['status']}, {a['model_calls']} model call(s) ({a['cached']} cached): {a['answer'][:160]}")
    DONE.append(2)
    print("✅ Phase 2 validation passed: English + Egyptian Arabic finance questions answered from finance_kpi, the "
          "stream in contract order")

    # %% Phase 3 — an upload and a question about it
    h_ops = {"Authorization": f"Bearer {tok['Operations']}"}
    conv = http.post(f"{BASE}/conversations", headers=h_ops).json()["conversation_id"]
    fix = ROOT / "Data" / "processed" / "rag" / "eval" / "uploads" / "fixtures" / "clean_D1.pdf"
    up = http.post(f"{BASE}/conversations/{conv}/uploads", headers=h_ops,
                   files={"file": (fix.name, fix.read_bytes())}, timeout=180)
    assert up.status_code == 201 and up.json()["accepted"], up.text[:300]
    a3, _ = ask(tok["Operations"], "What does my uploaded procedure say about the reefer pre-trip inspection?", conv)
    docs = [v for v in a3["evidence"].values() if v["tool"] == "search_documents"]
    assert docs and "conversation uploads" in (docs[0]["source"] or ""), a3["evidence"]
    DONE.append(3)
    print(f"✅ Phase 3 validation passed: the upload accepted ({up.json()['chunks']} chunks); the question "
          f"{a3['status']}, its document evidence includes the upload: {a3['answer'][:140]}")

    # %% Phase 4 — route advice
    ra = http.post(f"{BASE}/route-advice", headers=h_ops, json={"vessel_id": 36, "origin": "SGSIN",
                                                                "destination": "NLRTM"})
    assert ra.status_code == 202, ra.text
    THREADS.append(ra.json()["thread_id"])
    ev_ra = stream(f"http://127.0.0.1:{PORT}{ra.json()['events_url']}", tok["Operations"])
    r4 = next(d for e, d in ev_ra if e == "answer")
    assert r4["status"] == "ok" and r4["answer"].get("recommendation"), r4
    DONE.append(4)
    print(f"✅ Phase 4 validation passed: route advice {r4['status']}, recommendation "
          f"{r4['answer'].get('recommendation')}, {r4['model_calls']} model call(s)")

    # %% Phase 5 — the weekly pack
    g = weekly_pack.build_graph(None, checkpointer.saver())
    pending = [i for i in scheduling.describe_all(g, checkpointer.pool()) if i.state == "pending"]
    print(f"  pending live packs: {[i.thread_id for i in pending] or 'none'} — the decision through the API waits for "
          "the next real pack (the owner decides it)")
    DONE.append(5)
    print("✅ Phase 5 validation passed: reported (no real pack decided by the smoke)")
finally:
    server.terminate()
    try:
        server.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        server.kill()
    saver = checkpointer.saver()
    for t in THREADS:
        saver.delete_thread(t)
    with owner() as oc:
        n_audit = oc.execute("DELETE FROM api.audit_log WHERE at >= %s AND employee_id = ANY(%s)",
                             (started_at, IDS)).rowcount
        oc.execute("DELETE FROM api.conversations WHERE employee_id = ANY(%s)", (IDS,))
        n_logins = oc.execute("DELETE FROM api.logins WHERE employee_id = ANY(%s)", (IDS,)).rowcount
    print(f"clean-up: {n_logins} login(s), {n_audit} audit row(s), {len(THREADS)} thread(s) deleted; server stopped")

# %% Final Checkpoint
assert DONE == [1, 2, 3, 4, 5], DONE
print("✅ Final Checkpoint: 5 / 5 phases passed")
