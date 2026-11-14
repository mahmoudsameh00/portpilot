"""`RequestContext` — one plain ASGI middleware around every request (FastAPI plan §8 / §9), plain ASGI rather than
Starlette's `BaseHTTPMiddleware` so a streamed (SSE) response passes through untouched:

- **request id:** the client's `X-Request-ID` when it is a UUID, else a new one; on `request.state.request_id` and on
  the response (the access log, `audit_log`, Sentry and LangSmith carry the same id from P7);
- **body limit:** a declared `Content-Length` over the route's limit → 413 before the app reads anything; a chunked
  body is counted as it arrives and stopped at the limit;
- **security headers** on every response, including errors: `nosniff`, a CSP (`default-src 'none'` for JSON; the
  docs page gets the scripts it needs from jsdelivr), `frame-ancestors 'none'`, `X-Frame-Options`, `no-referrer`,
  `Cache-Control: no-store` (answers can hold level-2 figures);
- **unexpected exceptions** → a 500 problem body with the headers above (no exception text leaves the process);
- **the access log** (P7): one JSON line per request in `access_log` — method, the route *template* (never the path
  with its ids, never a query string, a body, a header or a question), status, milliseconds, employee id, request id;
  appended in a worker thread under the file lock (C3, C9).
"""
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import anyio
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from pipelines.api import config, errors
from pipelines.lib import shared_files

JSON_CSP = "default-src 'none'; frame-ancestors 'none'"
DOCS_CSP = ("default-src 'none'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "style-src https://cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' data: https://fastapi.tiangolo.com; "
            "connect-src 'self'; frame-ancestors 'none'")
DOCS_PATHS = ("/docs", "/redoc")


class BodyTooLarge(HTTPException):
    """An HTTPException on purpose: FastAPI turns any other error raised while it reads a body into a 400, but
    re-raises an HTTPException, which `errors` answers as a 413 problem."""

    def __init__(self):
        super().__init__(413)


def _rid(scope: Scope) -> str:
    for name, value in scope.get("headers", []):
        if name == b"x-request-id":
            try:
                return str(uuid.UUID(value.decode("latin-1")))
            except ValueError:
                break
    return str(uuid.uuid4())


def _limit(path: str) -> int:
    return config.UPLOAD_MAX_BYTES if path.endswith("/uploads") else config.MAX_BODY_BYTES


class RequestContext:
    def __init__(self, app: ASGIApp, access_log: Path | None = None):
        self.app, self.access_log = app, access_log

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        t0, status = time.perf_counter(), None
        try:
            status = await self._handle(scope, receive, send)
        finally:
            if self.access_log is not None:
                state = scope.get("state", {})
                line = json.dumps({"at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                                   "method": scope.get("method"),
                                   "route": getattr(scope.get("route"), "path", None) or "(unmatched)",
                                   "status": status,
                                   "ms": round((time.perf_counter() - t0) * 1000, 1),
                                   "employee_id": state.get("employee_id"), "request_id": state.get("request_id")})
                await anyio.to_thread.run_sync(shared_files.append_line, self.access_log, line)

    async def _handle(self, scope: Scope, receive: Receive, send: Send) -> int | None:
        rid = _rid(scope)
        scope.setdefault("state", {})["request_id"] = rid
        path, limit = scope.get("path", ""), _limit(scope.get("path", ""))
        csp = DOCS_CSP if path in DOCS_PATHS else JSON_CSP
        started = False
        status: int | None = None

        async def send_with_headers(message: Message) -> None:
            nonlocal started, status
            if message["type"] == "http.response.start":
                started, status = True, message["status"]
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"x-request-id"]
                headers += [(b"x-request-id", rid.encode()), (b"x-content-type-options", b"nosniff"),
                            (b"content-security-policy", csp.encode()), (b"x-frame-options", b"DENY"),
                            (b"referrer-policy", b"no-referrer"), (b"cache-control", b"no-store")]
                message = {**message, "headers": headers}
            await send(message)

        async def problem(status: int, body: dict) -> None:
            await send_with_headers({"type": "http.response.start", "status": status,
                                     "headers": [(b"content-type", errors.MEDIA.encode())]})
            await send({"type": "http.response.body", "body": json.dumps(body).encode()})

        declared = next((v for k, v in scope.get("headers", []) if k == b"content-length"), None)
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await problem(413, {"type": "urn:portpilot:problem:body_too_large", "title": errors.TITLES[413],
                                "status": 413, "detail": f"at most {limit} bytes", "request_id": rid})
            return 413
        seen = 0

        async def counted_receive() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    raise BodyTooLarge
            return message

        try:
            await self.app(scope, counted_receive, send_with_headers)
        except BodyTooLarge:
            if not started:
                await problem(413, {"type": "urn:portpilot:problem:body_too_large", "title": errors.TITLES[413],
                                    "status": 413, "detail": f"at most {limit} bytes", "request_id": rid})
        except Exception as exc:  # noqa: BLE001 — every unexpected failure becomes the same opaque 500
            if not started:
                await problem(500, errors.unexpected(exc, path, rid))
            else:
                errors.unexpected(exc, path, rid)    # a stream already started: report it, the client sees the cut
        return status
