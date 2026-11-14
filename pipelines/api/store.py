"""The API's own database login (`ports_api`, member of api_writer: schema `api` only, migration 023) — one pool per
process, as the tools' read-only pool (`pipelines/agents/tools/db.py`) and the checkpointer's.

Who reads what: an employee's email → id and role through the read-only pool (`api_writer` has nothing in `public`);
logins, tokens, conversations and the audit log through this one.
"""
import atexit
import os

from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from pipelines.lib.common import load_env

POOL_MAX = 4                 # PG_API_POOL_MAX in .env overrides
CONNECT_TIMEOUT_S = 5

_pool: ConnectionPool | None = None


def conninfo() -> str:
    load_env()
    e = os.environ
    if not (e.get("PG_API_USER") and e.get("PG_API_PASSWORD")):
        raise RuntimeError("PG_API_USER / PG_API_PASSWORD missing in .env: run db\\create_api_user.ps1")
    return make_conninfo(host=e["PGHOST"], port=e["PGPORT"], dbname=e["PGDATABASE"], user=e["PG_API_USER"],
                         password=e["PG_API_PASSWORD"], connect_timeout=CONNECT_TIMEOUT_S, options="-c search_path=api")


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(conninfo(), min_size=1, max_size=int(os.environ.get("PG_API_POOL_MAX") or POOL_MAX),
                               open=True, kwargs={"row_factory": dict_row, "autocommit": True})
        atexit.register(close)
    return _pool


def close() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
