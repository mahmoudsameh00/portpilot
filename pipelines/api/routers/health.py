"""Health (plan §3.1). `live` touches no dependency: it answers while the databases are down, so a supervisor of the
process can tell "the API is up" from "the API is ready". `ready` (a token needed: it names the components) checks
every store the products read and today's LLM request counts — names and numbers only, never an error text."""
from datetime import datetime, timedelta, timezone
from typing import Literal

import httpx
from fastapi import APIRouter, Response
from pydantic import BaseModel

from pipelines.agents import checkpointer
from pipelines.agents.tools import db, mongo
from pipelines.api import store
from pipelines.api.auth import Signed
from pipelines.api.schemas import Component, Ready
from pipelines.lib import qdrant_store

router = APIRouter(prefix="/health", tags=["health"])


class Live(BaseModel):
    status: Literal["live"] = "live"


@router.get("/live", response_model=Live)
def live() -> Live:
    return Live()


def _ok(check) -> bool:
    try:
        check()
        return True
    except Exception:  # noqa: BLE001 — any failure means "not ready"; the reason stays in the server's log
        return False


def _sql(pool) -> None:
    with pool.connection() as conn:
        conn.execute("SELECT 1")


@router.get("/ready", response_model=Ready)
def ready(response: Response, p: Signed) -> Ready:
    comps = [Component(name="postgres_readonly", ok=_ok(lambda: db.fetch("SELECT 1 AS ok"))),
             Component(name="postgres_agent_state", ok=_ok(lambda: _sql(checkpointer.pool()))),
             Component(name="postgres_api", ok=_ok(lambda: _sql(store.pool()))),
             Component(name="mongodb", ok=_ok(lambda: mongo.database().command("ping"))),
             Component(name="qdrant", ok=_ok(lambda: httpx.get(f"{qdrant_store.URL}/readyz",
                                                               timeout=3).raise_for_status()))]
    counts: dict[str, int] = {}
    if comps[1].ok:
        since = (datetime.now(timezone.utc) - timedelta(days=1)).date()        # every provider's "today"
        with checkpointer.pool().connection() as conn:
            # each scope's latest provider day (providers' days start in different time zones)
            for r in conn.execute("SELECT DISTINCT ON (scope) scope, requests AS n FROM agent_state.llm_daily_usage "
                                  "WHERE provider_day >= %s ORDER BY scope, provider_day DESC", (since,)).fetchall():
                counts[str(dict(r)["scope"])] = int(dict(r)["n"])
    status = "ready" if all(c.ok for c in comps) else "degraded"
    if status != "ready":
        response.status_code = 503
    return Ready(status=status, components=comps, llm_requests_today=counts)
