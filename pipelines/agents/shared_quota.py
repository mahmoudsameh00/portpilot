"""The LLM counters shared by every process (FastAPI plan C1 / C2, migration 023): the API and the scheduled CLIs run
at the same time, so a per-process count lets two of them both send the 500th request of the day.

- `reserve_day`: one atomic statement reserves a request before it is sent — `INSERT … ON CONFLICT DO UPDATE …
  WHERE requests < limit RETURNING`; no row back = the day's limit is reached. The first row of a day starts from the
  count the per-process file already holds for it (`seed`), so switching to the shared counter mid-day never resets it.
- `SharedBudget`: the per-minute limit (requests + estimated tokens) as a sliding-window estimate over two UTC-minute
  rows (the previous minute weighted by the share of it still inside the last 60 s); the current minute's row is locked
  (`FOR UPDATE`) while deciding, so two processes never both take the last slot. Over the limit → sleep until a slot
  frees: excess requests wait, they do not fail (C8 back-pressure lives in the API, before a run starts).
Both run on the checkpointer login (`ports_agent`, agent_writer's DML on agent_state); every LLM caller already
needs that database for its checkpoints, so this adds no new failure mode.
"""
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg_pool import ConnectionPool

from pipelines.lib.common import load_env

KEEP_MINUTE_ROWS = timedelta(days=1)


class SharedCounters:
    def __init__(self, pool: ConnectionPool):
        self.pool = pool

    def reserve_day(self, scope: str, day: str, limit: int | None, seed: int = 0) -> int | None:
        """The day's count after reserving one request, or None when `limit` is already reached."""
        with self.pool.connection() as conn:
            row = conn.execute(
                "INSERT INTO agent_state.llm_daily_usage AS u (scope, provider_day, requests) VALUES (%s, %s, %s) "
                "ON CONFLICT (scope, provider_day) DO UPDATE SET requests = u.requests + 1, updated_at = now() "
                "WHERE %s::int IS NULL OR u.requests < %s::int RETURNING u.requests",
                (scope, day, seed + 1, limit, limit)).fetchone()
        if row is None:
            return None
        n = int(_first(row))
        return None if limit is not None and n > limit else n      # a seed already at the limit refuses too

    def day_count(self, scope: str, day: str) -> int:
        with self.pool.connection() as conn:
            row = conn.execute("SELECT requests FROM agent_state.llm_daily_usage WHERE scope = %s AND "
                               "provider_day = %s", (scope, day)).fetchone()
        return int(_first(row)) if row else 0

    def try_minute(self, scope: str, rpm: int, tpm: int, tokens: int, now: datetime | None = None
                   ) -> tuple[datetime | None, float]:
        """(the minute reserved, 0) — or (None, seconds to wait) when the sliding window is full."""
        now = now or datetime.now(timezone.utc)
        cur = now.replace(second=0, microsecond=0)
        prev_weight = 1 - (now - cur).total_seconds() / 60
        with self.pool.connection() as conn, conn.transaction():
            conn.execute("INSERT INTO agent_state.llm_minute_usage (scope, minute) VALUES (%s, %s) "
                         "ON CONFLICT DO NOTHING", (scope, cur))
            c = conn.execute("SELECT requests, tokens FROM agent_state.llm_minute_usage WHERE scope = %s AND "
                             "minute = %s FOR UPDATE", (scope, cur)).fetchone()
            p = conn.execute("SELECT requests, tokens FROM agent_state.llm_minute_usage WHERE scope = %s AND "
                             "minute = %s", (scope, cur - timedelta(minutes=1))).fetchone()
            c_req, c_tok = _pair(c)
            p_req, p_tok = _pair(p)
            if c_req + p_req * prev_weight + 1 <= rpm and c_tok + p_tok * prev_weight + tokens <= tpm:
                conn.execute("UPDATE agent_state.llm_minute_usage SET requests = requests + 1, tokens = tokens + %s "
                             "WHERE scope = %s AND minute = %s", (tokens, scope, cur))
                return cur, 0.0
        if c_req + 1 > rpm or c_tok + tokens > tpm:        # this minute is full: wait for the next one
            return None, (cur + timedelta(minutes=1) - now).total_seconds() + 0.1
        return None, max(0.5, min(5.0, 60 * prev_weight))  # the previous minute's weight still decays: re-check soon

    def adjust_minute(self, scope: str, minute: datetime, delta_tokens: int) -> None:
        if delta_tokens:
            with self.pool.connection() as conn:
                conn.execute("UPDATE agent_state.llm_minute_usage SET tokens = greatest(0, tokens + %s) "
                             "WHERE scope = %s AND minute = %s", (delta_tokens, scope, minute))

    def prune_minutes(self) -> int:
        with self.pool.connection() as conn:
            return conn.execute("DELETE FROM agent_state.llm_minute_usage WHERE minute < %s",
                                (datetime.now(timezone.utc) - KEEP_MINUTE_ROWS,)).rowcount


def _first(row) -> Any:
    return next(iter(row.values())) if isinstance(row, dict) else row[0]


def _pair(row) -> tuple[int, int]:
    if row is None:
        return 0, 0
    return (int(row["requests"]), int(row["tokens"])) if isinstance(row, dict) else (int(row[0]), int(row[1]))


class SharedBudget:
    """Same interface as `pipelines.lib.embeddings.Budget` (`wait(tokens)` → seconds waited, `record(tokens)`), over
    `SharedCounters`: `wait` reserves the estimate in the shared minute; `record` corrects it to the tokens the
    provider reported. One reservation per thread at a time (the LLM call between the two runs in that thread)."""

    def __init__(self, counters: SharedCounters, scope: str, rpm: int, tpm: int):
        self.counters, self.scope, self.rpm, self.tpm = counters, scope, rpm, tpm
        self._held = threading.local()

    def wait(self, tokens: int) -> float:
        waited = 0.0
        while True:
            minute, pause = self.counters.try_minute(self.scope, self.rpm, self.tpm, tokens)
            if minute is not None:
                self._held.reservation = (minute, tokens)
                return waited
            time.sleep(pause)
            waited += pause

    def record(self, tokens: int) -> None:
        held = getattr(self._held, "reservation", None)
        if held is None:
            return
        self._held.reservation = None
        minute, reserved = held
        self.counters.adjust_minute(self.scope, minute, tokens - reserved)


_shared: SharedCounters | None = None


def shared() -> SharedCounters | None:
    """The process's counters on the checkpointer pool, or None when no checkpointer login is configured (the CI,
    a machine without the databases): then llm.py keeps its per-process files, as before."""
    global _shared
    if _shared is None:
        load_env()
        if not (os.environ.get("PG_AGENT_USER") and os.environ.get("PG_AGENT_PASSWORD")):
            return None
        from pipelines.agents import checkpointer
        _shared = SharedCounters(checkpointer.pool())
    return _shared
