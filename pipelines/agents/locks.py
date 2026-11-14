"""Cross-process graph mutation locks shared by the API, CLI and scheduler.

Use the checkpoint login, never the API-only login. Session locks use a dedicated connection so they remain
held across checkpoint transactions and are released even when graph execution raises.
"""
import hashlib
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from pipelines.agents import checkpointer


class ThreadBusy(RuntimeError):
    pass


@contextmanager
def thread_lock(thread_id: str) -> Iterator[None]:
    key = int.from_bytes(hashlib.sha256(thread_id.encode()).digest()[:8], "big", signed=True)
    info = checkpointer.conninfo("PG_AGENT_USER", "PG_AGENT_PASSWORD")
    with psycopg.connect(info, autocommit=True) as conn:
        row = conn.execute("SELECT pg_try_advisory_lock(%s)", (key,)).fetchone()
        if not (row and row[0]):
            raise ThreadBusy("this thread is being worked on by another run")
        try:
            yield
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (key,))
