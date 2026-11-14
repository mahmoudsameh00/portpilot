"""`create_app()` — the FastAPI application (FastAPI plan; P0 the skeleton, P3 auth, errors and the security layer;
runs and the product routers follow in P4–P6).

Every route lives under `BASE` (plan A8). The app is built by a factory so the checks get a fresh one per phase and
`Serve.py` hands uvicorn the factory, not a module-level object.

Layers, outside in: `RequestContext` (request id, body limit, security headers, the opaque 500) → CORS (the UI's
origin only, no credentials: the token travels in a header, not a cookie) → FastAPI's handlers (`errors`) → routes.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pipelines.agents import llm, roles, scheduling, shared_quota
from pipelines.api import config, errors, runs, store
from pipelines.api.middleware import RequestContext
from pipelines.api.routers import ask, auth, finance, health, me, operations, packs, uploads, views
from pipelines.api.uploads import UploadSessions
from pipelines.lib import retrieval
from pipelines.lib.common import project_root

BASE = "/api/v1"
log = logging.getLogger(__name__)
VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    app.state.runner.shutdown()     # queued runs are dropped (their threads wait at their checkpoints)
    store.close()


_DEFAULT = object()


def count_query_embedding() -> None:
    """D-F2-2: one Gemini query embedding = one request of the shared daily counter (no limit enforced: the counts
    show in `/health/ready`; a refused count never blocks a search)."""
    try:
        counters = shared_quota.shared()
        if counters is not None:
            counters.reserve_day("gemini/gemini-embedding-2", llm.provider_day("gemini"), None)
    except Exception as exc:  # noqa: BLE001 — counting is reporting; the search goes on
        log.warning("query-embedding count failed: %s", type(exc).__name__)


def create_app(roles_factory=roles.Roles, reports_dir=None, pack_prefix: str = scheduling.LIVE_PREFIX,
               access_log=_DEFAULT) -> FastAPI:
    """`roles_factory` builds the models for one run (`Roles` = the real ones over llm.py; a check passes
    `FakeRoles`). A new set per run: a model one run found unavailable is not skipped by every later run.
    `reports_dir` / `pack_prefix`: where packs publish and which threads are packs — a check passes its own, so its
    test pack never touches the scheduler's live replay (`weekly_pack:live:…`) or `reports/`."""
    app = FastAPI(title="PortPilot API", version=VERSION, lifespan=lifespan,
                  description="Ask the supervisor, decide weekly packs, route advice, voyage-watch alerts, uploads.")
    app.state.runner = runs.Runner()
    app.state.roles_factory = roles_factory
    app.state.uploads = UploadSessions()
    app.state.reports_dir = reports_dir or project_root() / "reports"
    app.state.pack_prefix = pack_prefix
    log_file = (project_root() / "reports" / "_log" / "api.jsonl" if access_log is _DEFAULT
                else cast(Path | None, access_log))
    retrieval.ON_QUERY_EMBED = count_query_embedding
    errors.register(app)
    app.add_middleware(CORSMiddleware, allow_origins=config.cors_origins(), allow_credentials=False,
                       allow_methods=["GET", "POST", "DELETE"],
                       allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Last-Event-ID"],
                       expose_headers=["X-Request-ID", "Retry-After"], max_age=600)
    app.add_middleware(RequestContext, access_log=log_file)     # added last = the outermost layer
    for r in (health.router, auth.router, me.router, ask.router, uploads.router, packs.router, operations.router,
              views.router, packs.dashboard, finance.router):   # /finance/pack before /finance/{dataset}
        app.include_router(r, prefix=BASE)
    return app
