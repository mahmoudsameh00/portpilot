"""The schedules off Windows (Staging readiness plan P5, ADR-071): the weekly pack and the voyage watch, fired by a
small loop in the `scheduler` container instead of Windows Task Scheduler (ADR-054 / ADR-058 keep their meaning).

Command (inside the image; from the project root):
    python pipelines/scripts/ops/Scheduler_service.py              run for ever (the compose service `scheduler`)
    python pipelines/scripts/ops/Scheduler_service.py --plan       print each job's next firing and exit
    python pipelines/scripts/ops/Scheduler_service.py --once weekly_pack | voyage_watch
                                                                  fire one job now (an operator's manual run)

The jobs and their Task Scheduler equivalents (times in Africa/Cairo, the owner's clock and Sentry's cron monitor's):
    weekly_pack   Monday 10:30          `Weekly_pack.py scheduled`   1 h limit   catch-up 12 h ("start when available")
    voyage_watch  every day 10:30, 22:30 `Voyage_watch.py scheduled` 1 h limit   catch-up 6 h
Rules kept from the Windows tasks: one job at a time (each CLI also holds its own lock file in reports/_log/), no
second instance, a run past its limit is stopped, a missed firing runs once when the service comes back inside the
catch-up window and is recorded as `skipped` after it. On the very first start (no state file) nothing fires: the
last due instant is recorded as already handled, so a new deployment never starts a pack by surprise.

Reads:   the environment of the container (the CLIs read theirs: PACK_RUN_AS, WATCH_RUN_AS, the databases, the keys).
Writes:  reports/_log/scheduler_state.json (the last instant handled per job), reports/_log/scheduler.jsonl (one line
         per firing: job, due, started, exit code, seconds); the CLIs write their own logs.
Re-run:  safe; SIGTERM / Ctrl+C stops the loop (a running job is terminated, its thread waits at its checkpoint).
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
TZ = ZoneInfo("Africa/Cairo")
LOG_DIR = ROOT / "reports" / "_log"
STATE = LOG_DIR / "scheduler_state.json"
JOURNAL = LOG_DIR / "scheduler.jsonl"
TICK_S = 30


@dataclass(frozen=True)
class Job:
    name: str
    weekdays: tuple[int, ...]          # Monday = 0
    times: tuple[tuple[int, int], ...]  # (hour, minute), local
    argv: tuple[str, ...]
    limit_s: int
    catch_up: timedelta


JOBS = (
    Job("weekly_pack", (0,), ((10, 30),), ("pipelines/scripts/agents/Weekly_pack.py", "scheduled"), 3600,
        timedelta(hours=12)),
    Job("voyage_watch", tuple(range(7)), ((10, 30), (22, 30)), ("pipelines/scripts/agents/Voyage_watch.py", "scheduled"),
        3600, timedelta(hours=6)),
)


def last_due(job: Job, now: datetime) -> datetime:
    """The latest scheduled instant at or before `now` (aware, Africa/Cairo)."""
    local = now.astimezone(TZ)
    for days_back in range(0, 8):
        day = (local - timedelta(days=days_back)).date()
        if day.weekday() not in job.weekdays:
            continue
        for h, m in sorted(job.times, reverse=True):
            t = datetime(day.year, day.month, day.day, h, m, tzinfo=TZ)
            if t <= local:
                return t
    raise AssertionError(f"{job.name}: no instant in the last week")


def next_due(job: Job, now: datetime) -> datetime:
    local = now.astimezone(TZ)
    for days_ahead in range(0, 8):
        day = (local + timedelta(days=days_ahead)).date()
        if day.weekday() not in job.weekdays:
            continue
        for h, m in sorted(job.times):
            t = datetime(day.year, day.month, day.day, h, m, tzinfo=TZ)
            if t > local:
                return t
    raise AssertionError(f"{job.name}: no instant in the next week")


def decide(job: Job, handled: datetime | None, now: datetime) -> tuple[str, datetime]:
    """("fire" | "skip" | "wait" | "init", due instant). `handled` = the last instant already fired or skipped."""
    due = last_due(job, now)
    if handled is None:
        return "init", due
    if due <= handled:
        return "wait", due
    if now - due > job.catch_up:
        return "skip", due
    return "fire", due


def load_state() -> dict[str, datetime]:
    try:
        raw = json.loads(STATE.read_text(encoding="utf-8"))
        return {k: datetime.fromisoformat(v) for k, v in raw.items()}
    except (OSError, ValueError):
        return {}


def save_state(state: dict[str, datetime]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps({k: v.isoformat() for k, v in sorted(state.items())}, indent=1) + "\n",
                   encoding="utf-8", newline="\n")
    tmp.replace(STATE)


def journal(rec: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps(rec, ensure_ascii=False), flush=True)


_current: subprocess.Popen | None = None
_stopping = False


def run_job(job: Job, due: datetime | None) -> int:
    global _current
    started = datetime.now(TZ)
    t0 = time.monotonic()
    code: int
    try:
        _current = subprocess.Popen([sys.executable, *job.argv], cwd=ROOT)
        try:
            code = _current.wait(timeout=job.limit_s)
        except subprocess.TimeoutExpired:
            _current.terminate()
            try:
                _current.wait(timeout=30)
            except subprocess.TimeoutExpired:
                _current.kill()
            code = -1
    finally:
        _current = None
    journal({"job": job.name, "due": due.isoformat() if due else None, "started": started.isoformat(),
             "exit": code, "seconds": round(time.monotonic() - t0, 1), "limit_hit": code == -1})
    return code


def _stop(signum, _frame) -> None:
    global _stopping
    _stopping = True
    if _current is not None and _current.poll() is None:
        _current.terminate()


def tick(now: datetime, state: dict[str, datetime], runner=run_job) -> dict[str, datetime]:
    for job in JOBS:
        if _stopping:
            break
        action, due = decide(job, state.get(job.name), now)
        if action == "init":
            state[job.name] = due
            journal({"job": job.name, "init": True, "handled_until": due.isoformat()})
        elif action == "skip":
            state[job.name] = due
            journal({"job": job.name, "due": due.isoformat(), "skipped": True,
                     "reason": f"missed by more than {job.catch_up}"})
        elif action == "fire":
            state[job.name] = due           # recorded before the run: a crash mid-run is not retried in a loop
            save_state(state)
            runner(job, due)
        save_state(state)
    return state


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--plan", action="store_true", help="print the next firing of each job and exit")
    ap.add_argument("--once", choices=[j.name for j in JOBS], help="fire one job now and exit with its code")
    a = ap.parse_args()
    now = datetime.now(TZ)
    if a.plan:
        state = load_state()
        for job in JOBS:
            handled = state.get(job.name)
            print(f"{job.name:<13} next {next_due(job, now).isoformat()}  last handled "
                  f"{handled.isoformat() if handled else '-'}")
        return
    if a.once:
        sys.exit(run_job(next(j for j in JOBS if j.name == a.once), None))
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    print(f"PortPilot scheduler ({os.environ.get('PORTPILOT_ENV', 'local')}): "
          + ", ".join(f"{j.name} next {next_due(j, now):%a %Y-%m-%d %H:%M}" for j in JOBS), flush=True)
    state = load_state()
    while not _stopping:
        state = tick(datetime.now(TZ), state)
        for _ in range(TICK_S):
            if _stopping:
                break
            time.sleep(1)


if __name__ == "__main__":
    main()
