"""One error body for every failure (FastAPI plan §7): RFC 9457 `application/problem+json`
`{type, title, status, detail, request_id}`. `detail` passes `redact()`; no stack trace, SQL, path, key or the
client's own input ever leaves the API (FastAPI's default 422 echoes the input — a password among it — so it is
replaced here).

A graph's own stop statuses (`partial`, `not_permitted`, `not_in_data`, …) are answers (200), not errors.
"""
import logging

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout
from starlette.exceptions import HTTPException as StarletteHTTPException

from pipelines.agents import llm, monitoring
from pipelines.lib.common import redact

log = logging.getLogger(__name__)
MEDIA = "application/problem+json"
QUOTA_RETRY_S = 3600                   # P4 replaces it with the seconds to the provider's day reset
DATABASE_RETRY_S = 30
TITLES = {400: "bad request", 401: "not signed in", 403: "not allowed", 404: "not found", 405: "method not allowed",
          409: "conflict", 413: "body too large", 415: "unsupported media type", 422: "invalid request",
          429: "too many requests", 500: "internal error", 503: "service unavailable"}


class ApiError(Exception):
    """`extra` = RFC 9457 extension members (e.g. an upload's refusal reasons); never the client's own input."""

    def __init__(self, status: int, detail: str = "", *, slug: str | None = None, headers: dict | None = None,
                 extra: dict | None = None):
        super().__init__(detail)
        self.status, self.detail, self.headers, self.extra = status, detail, headers or {}, extra or {}
        self.slug = slug or TITLES.get(status, "error").replace(" ", "_")


def request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def problem(request: Request, status: int, detail: str = "", *, slug: str | None = None,
            headers: dict | None = None, extra: dict | None = None) -> JSONResponse:
    title = TITLES.get(status, "error")
    body = {**(extra or {}), "type": f"urn:portpilot:problem:{slug or title.replace(' ', '_')}", "title": title,
            "status": status, "detail": redact(detail)[:500], "request_id": request_id(request)}
    return JSONResponse(body, status_code=status, media_type=MEDIA, headers=headers)


def _validation_detail(exc: RequestValidationError) -> str:
    """Where and what, never the value: `body.email: Field required; body.password: …`."""
    parts = []
    for e in exc.errors()[:8]:
        loc = ".".join(str(x) for x in e.get("loc", ()))
        parts.append(f"{loc}: {e.get('msg', 'invalid')}")
    return "; ".join(parts)


def register(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return problem(request, exc.status, exc.detail, slug=exc.slug, headers=exc.headers, extra=exc.extra)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        # routing's 404 / 405 and Starlette's own raises: the status kept, Starlette's wording not echoed
        return problem(request, exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        return problem(request, 422, _validation_detail(exc))

    @app.exception_handler(llm.Exhausted)
    async def _quota(request: Request, exc: llm.Exhausted):
        return problem(request, 503, "the free model quota is spent for now; try again later", slug="quota",
                       headers={"Retry-After": str(QUOTA_RETRY_S)})

    @app.exception_handler(psycopg.OperationalError)
    async def _database(request: Request, exc: psycopg.OperationalError):
        log.warning("database unavailable: %s", redact(str(exc))[:200])
        return problem(request, 503, "a database is not reachable", slug="database",
                       headers={"Retry-After": str(DATABASE_RETRY_S)})

    @app.exception_handler(PoolTimeout)
    async def _pool(request: Request, exc: PoolTimeout):
        return problem(request, 503, "every database connection is busy", slug="database_busy",
                       headers={"Retry-After": str(DATABASE_RETRY_S)})
    # anything else is answered by `middleware.RequestContext` (500): Starlette sends a handler registered for
    # `Exception` from its outermost layer, where the security headers would be missing


def unexpected(exc: BaseException, path: str, rid: str | None) -> dict:
    """The 500 body; the exception goes to Sentry (when on) and the log, never to the client."""
    monitoring.capture(exc, request_id=rid, route=path)
    log.error("unexpected %s on %s (request %s)", type(exc).__name__, path, rid)
    return {"type": "urn:portpilot:problem:internal_error", "title": TITLES[500], "status": 500,
            "detail": "something went wrong; quote the request id", "request_id": rid}
