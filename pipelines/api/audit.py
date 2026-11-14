"""`api.audit_log` (ADR-014 redesign, migration 023): one row per data decision — a sign-in, a sign-out, a thread
read, a refused part, a pack decision, an upload verdict. Never a password, a token, a question's text or an answer:
`detail` holds small structured facts only.

A failed audit write never fails the request it describes (the request already happened or was refused); it is
logged as a WARNING, which Sentry receives (ADR-062), so a gap in the log is visible.
"""
import json
import logging

from pipelines.api import store
from pipelines.lib.common import redact

log = logging.getLogger(__name__)


def record(*, employee_id: int | None, resource_type: str, action: str, decision: str, request_id: str | None,
           resource_id: str | None = None, trace_id: str | None = None, detail: dict | None = None) -> None:
    assert decision in ("allowed", "denied"), decision
    try:
        with store.pool().connection() as conn:
            conn.execute("INSERT INTO audit_log (employee_id, request_id, trace_id, resource_type, resource_id, "
                         "action, decision, detail) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
                         (employee_id, request_id, trace_id, resource_type, resource_id, action, decision,
                          json.dumps(detail or {}, default=str)))
    except Exception as exc:  # noqa: BLE001 — the audit never takes the request down; the gap is reported
        log.warning("audit_log write failed (%s %s %s): %s", resource_type, action, decision,
                    redact(f"{type(exc).__name__}: {exc}")[:300])
