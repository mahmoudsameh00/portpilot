"""Load test (FastAPI plan §4 / §10): the LLM state shared across processes — C1 the daily counter, C2 the per-minute
limiter, C3 the cache appends, C4 single-flight, C6 the connection pools — with fake models (no provider is called)
on the real PostgreSQL. C5 / C7–C9 and cross-user isolation join when the API's run executor exists (P4).

Plan:    dev/history/archive/2026-11-05_FastAPI_plan.md (approved 2026-11-03), P2.
Run:     uv run python dev/tools/run.py dev/checks/api/Load_test.py  (from the project root; ≈ 4 minutes, C2 waits
         for real minutes)

Reads:   .env (the checkpointer login: the shared counters live in agent_state).
Writes:  a throw-away temp folder (the fake models' caches and quota files); rows of agent_state.llm_daily_usage /
         llm_minute_usage under the scope `loadtest/<run id>…`, deleted at the end. Nothing tracked.
Re-run:  safe (a new run id each time).

Phases
1. C1 — 4 processes × 50 different requests against a daily limit of 120 → exactly 120 sent, 80 refused
   (`Exhausted`), the shared counter = 120, the `usage.json` export = 120.
2. C2 — 3 processes × 3 requests against 4 requests / minute → every request sent (they wait, none fails), at most 4
   in any UTC minute, the requests spread over ≥ 3 minutes.
3. C3 — 8 processes × 200 different requests into one cache file + 8 × 50 tool-cache entries into one file → 1,600 /
   400 complete JSON lines, no key twice, a fresh reader sees them all.
4. C4 — 2 processes × 10 threads send the same request at the same instant → 1 provider call, 19 cache hits, 20 equal
   answers.
5. C6 — the pool sizes follow `.env` (`PG_AGENT_POOL_MAX`, `PG_RO_POOL_MAX`) with today's defaults otherwise; the
   connection budget of plan §4 (≈ 40) is below `max_connections`; the peak of `pg_stat_activity` while 8 processes
   ran (phase 3) is below 60.
Final Checkpoint (pending phases listed).
"""
# %% Setup
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

from pipelines.agents import checkpointer, llm  # noqa: E402

PROVIDER = "loadtest"


class FakeChat:
    """Stands for a provider's chat model: answers from the request text after `delay` seconds; counts its calls."""

    def __init__(self, delay: float):
        self.delay, self.calls = delay, 0

    def invoke(self, messages):
        self.calls += 1
        time.sleep(self.delay)
        return AIMessage(content="answer to " + "|".join(str(m.content) for m in messages))


def fake_llm(tmp: Path, model: str, rpm: int, rpd: int | None, delay: float) -> tuple[llm.LLM, FakeChat]:
    llm.PROVIDERS[PROVIDER] = {"key": "LOADTEST_KEY", "rpm": rpm, "tpm": 10 ** 9, "rpd": rpd, "scope": "model",
                               "day_tz": "UTC", "candidates": []}
    chat = FakeChat(delay)
    m = llm.LLM(PROVIDER, model, cache_dir=tmp, quota=llm.QuotaState(tmp))
    m._chat = chat                                    # never builds a real client
    return m, chat


def worker(phase: str, run: str, no: int, tmp: Path, start_at: float) -> dict:
    """One process of a phase; prints one JSON line."""
    time.sleep(max(0.0, start_at - time.time()))      # every process starts at the same instant
    if phase == "c1":
        m, chat = fake_llm(tmp, f"{run}-c1", rpm=100_000, rpd=120, delay=0.0)
        ok = refused = 0
        for i in range(50):
            try:
                m.invoke([HumanMessage(f"c1 {no} {i}")])
                ok += 1
            except llm.Exhausted:
                refused += 1
        return {"ok": ok, "refused": refused, "calls": chat.calls}
    if phase == "c2":
        m, chat = fake_llm(tmp, f"{run}-c2", rpm=4, rpd=None, delay=0.0)
        sent = []
        for i in range(3):
            m.invoke([HumanMessage(f"c2 {no} {i}")])
            sent.append(time.time())
        return {"sent": sent, "calls": chat.calls}
    if phase == "c3":
        from pipelines.agents.tools import external
        m, chat = fake_llm(tmp, f"{run}-c3", rpm=100_000, rpd=None, delay=0.0)
        for i in range(200):
            m.invoke([HumanMessage(f"c3 {no} {i}")])
        cache = external.ExternalCache(f"{run}-tool", folder=tmp)
        for i in range(50):
            cache.put(f"{no}-{i}", {"no": no, "i": i}, {"value": i}, True)
        return {"calls": chat.calls}
    if phase == "c4":
        m, chat = fake_llm(tmp, f"{run}-c4", rpm=100_000, rpd=None, delay=2.0)
        out: list[tuple[str, bool]] = []
        lock = threading.Lock()

        def ask():
            r = m.invoke([HumanMessage("c4 the same question")])
            with lock:
                out.append((str(r.message.content) if r.message else "", r.cached))
        threads = [threading.Thread(target=ask) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return {"calls": chat.calls, "answers": [a for a, _ in out], "cached": sum(c for _, c in out)}
    if phase == "c6":
        from pipelines.agents.tools import db
        return {"agent_max": checkpointer.pool().max_size, "ro_max": db.pool().max_size}
    raise SystemExit(f"unknown phase {phase}")


if len(sys.argv) > 1 and sys.argv[1] == "--worker":
    _, _, ph, rid, wno, folder, at = sys.argv
    print(json.dumps(worker(ph, rid, int(wno), Path(folder), float(at))))
    sys.exit(0)

RUN = "lt" + uuid.uuid4().hex[:8]
TMP = Path(tempfile.mkdtemp(prefix="load_test_"))
DONE: list[int] = []


def run_workers(phase: str, n: int, env: dict | None = None, timeout: float = 600) -> list[dict]:
    start_at = time.time() + 3.0                      # time for every process to import before the start
    procs = [subprocess.Popen([sys.executable, __file__, "--worker", phase, RUN, str(i), str(TMP), str(start_at)],
                              cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              env={**os.environ, **(env or {})}) for i in range(n)]
    outs = []
    for p in procs:
        out, err = p.communicate(timeout=timeout)
        assert p.returncode == 0, f"worker failed ({p.returncode}): {err[-1500:]}"
        outs.append(json.loads(out.strip().splitlines()[-1]))
    return outs


def sql(query: str, params=()) -> list:
    with checkpointer.pool().connection() as conn:
        return conn.execute(query, params).fetchall()


def cleanup() -> int:
    return sum(len(sql(f"DELETE FROM agent_state.{t} WHERE scope LIKE %s RETURNING 1", (f"{PROVIDER}/{RUN}%",)))
               for t in ("llm_daily_usage", "llm_minute_usage"))


fake_llm(TMP, f"{RUN}-setup", rpm=1, rpd=None, delay=0.0)         # registers the fake provider in this process
assert llm.QuotaState(TMP).counters is not None, "the checkpointer login is not configured: nothing shared to test"
print(f"run {RUN}, temp folder {TMP}")


# %% Phase 1 — C1: the daily counter
outs = run_workers("c1", 4)
ok, refused = sum(o["ok"] for o in outs), sum(o["refused"] for o in outs)
day = llm.provider_day(PROVIDER)
shared = sql("SELECT requests FROM agent_state.llm_daily_usage WHERE scope = %s AND provider_day = %s",
             (f"{PROVIDER}/{RUN}-c1", day))
export = json.loads((TMP / "usage.json").read_text(encoding="utf-8"))[day][f"{PROVIDER}/{RUN}-c1"]
assert (ok, refused) == (120, 80), (ok, refused)
assert sum(o["calls"] for o in outs) == 120, outs
assert shared and shared[0]["requests"] == 120, shared
assert export == 120, export
DONE.append(1)
print(f"✅ Phase 1 validation passed: 4 processes × 50 against 120 / day → {ok} sent, {refused} refused; shared "
      f"counter {shared[0]['requests']}, usage.json export {export}")


# %% Phase 2 — C2: the per-minute limiter
t0 = time.time()
outs = run_workers("c2", 3)
sent = sorted(t for o in outs for t in o["sent"])
minutes = sql("SELECT minute, requests FROM agent_state.llm_minute_usage WHERE scope = %s ORDER BY minute",
              (f"{PROVIDER}/{RUN}-c2",))
per_minute = [r["requests"] for r in minutes if r["requests"]]
assert len(sent) == 9 and sum(o["calls"] for o in outs) == 9, outs
assert sum(per_minute) == 9 and max(per_minute) <= 4, per_minute
assert len(per_minute) >= 3, f"9 requests at 4 / minute need at least 3 minutes, got {per_minute}"
DONE.append(2)
print(f"✅ Phase 2 validation passed: 9 requests from 3 processes at 4 / minute → all sent, per minute {per_minute}, "
      f"{time.time() - t0:.0f} s")


# %% Phase 3 — C3: cache appends from 8 processes (and the C6 connection peak)
peak = {"n": 0}
stop = threading.Event()


def watch_connections():
    while not stop.is_set():
        n = sql("SELECT count(*) AS n FROM pg_stat_activity WHERE datname = current_database()")[0]["n"]
        peak["n"] = max(peak["n"], n)
        stop.wait(0.5)


watcher = threading.Thread(target=watch_connections, daemon=True)
watcher.start()
outs = run_workers("c3", 8)
stop.set()
watcher.join()
cache_file = TMP / PROVIDER / f"{llm.slug(RUN + '-c3')}.jsonl"
lines = cache_file.read_text(encoding="utf-8").splitlines()
recs = [json.loads(line) for line in lines]
tool_lines = (TMP / f"{RUN}-tool.jsonl").read_text(encoding="utf-8").splitlines()
tool_keys = {json.loads(line)["key"] for line in tool_lines}
fresh, _ = fake_llm(TMP, f"{RUN}-c3", rpm=100_000, rpd=None, delay=0.0)
assert sum(o["calls"] for o in outs) == 1600, outs
assert len(lines) == 1600 and len({r["key"] for r in recs}) == 1600, (len(lines), len({r["key"] for r in recs}))
assert len(tool_lines) == 400 and len(tool_keys) == 400, (len(tool_lines), len(tool_keys))
assert len(fresh.cache) == 1600
DONE.append(3)
print(f"✅ Phase 3 validation passed: 8 processes → 1,600 / 1,600 complete cache lines, 400 / 400 tool-cache lines, "
      f"no key twice; a fresh reader sees 1,600 (connection peak {peak['n']})")


# %% Phase 4 — C4: single-flight
outs = run_workers("c4", 2)
answers = [a for o in outs for a in o["answers"]]
calls, cached = sum(o["calls"] for o in outs), sum(o["cached"] for o in outs)
assert len(answers) == 20 and len(set(answers)) == 1 and answers[0], answers[:3]
assert calls == 1 and cached == 19, (calls, cached)
DONE.append(4)
print(f"✅ Phase 4 validation passed: 20 identical requests (2 processes × 10 threads) → {calls} provider call, "
      f"{cached} cache hits, 1 distinct answer")


# %% Phase 5 — C6: pool sizes and the connection budget
default = run_workers("c6", 1, env={"PG_AGENT_POOL_MAX": "", "PG_RO_POOL_MAX": ""})[0]
api = run_workers("c6", 1, env={"PG_AGENT_POOL_MAX": "6", "PG_RO_POOL_MAX": "8"})[0]
max_conn = int(sql("SHOW max_connections")[0]["max_connections"])
budget = (8 + 6) + 2 * (checkpointer.POOL_MAX + 4) + (2 + 4) + 5 + 10   # API + 2 scheduled CLIs + a hand CLI + BI + checks
assert (default["agent_max"], default["ro_max"]) == (2, 4), default
assert (api["agent_max"], api["ro_max"]) == (6, 8), api
assert budget < max_conn and peak["n"] < 60, (budget, max_conn, peak)
DONE.append(5)
print(f"✅ Phase 5 validation passed: pools 2 / 4 by default, 6 / 8 from .env; budget {budget} < max_connections "
      f"{max_conn}; peak {peak['n']} < 60 while 8 processes ran")


# %% Final Checkpoint
PHASES = {1: "C1 daily counter", 2: "C2 per-minute limiter", 3: "C3 cache appends", 4: "C4 single-flight",
          5: "C6 pools + connection budget"}
removed = cleanup()
print(f"clean-up: {removed} counter row(s) of {RUN} deleted")
pending = [f"{k} {v}" for k, v in PHASES.items() if k not in DONE]
assert DONE == sorted(DONE) and set(DONE) <= set(PHASES)
print(f"Final Checkpoint: done {DONE}; pending: {pending}")
print(f"✅ Final Checkpoint: {len(DONE)} / {len(PHASES)} phases passed")
