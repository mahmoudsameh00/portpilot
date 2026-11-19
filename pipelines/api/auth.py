"""Sign-in and the bearer token → the employee (FastAPI plan §6, owner A1). The only place `RunContext.user` comes
from in the API: a request body never carries an employee id.

- `sign_in`: the employee's email (read-only pool: employees → id) + the password checked against `api.logins`
  (scrypt, `passwords.py`); the same 401 for an unknown email, a disabled or locked login and a wrong password, and the
  same work for each (an unknown email is checked against a dummy hash), so neither the answer nor its timing tells
  which emails exist. 5 wrong passwords in a row lock the login for 15 minutes. Success → 32 random bytes as the token;
  only their SHA-256 is stored, with an 8 h expiry.
- `principal` (a FastAPI dependency): `Authorization: Bearer <token>` → a live, unrevoked, unexpired token of an
  enabled login → `context.load_user` from PostgreSQL **at every request**, so a role change takes effect at once.
- `sign_out`: revokes the token.
Every sign-in, refused or not, is one `audit_log` row.
"""
import hashlib
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Any, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pipelines.agents.tools import context, db
from pipelines.api import audit, config, passwords, store
from pipelines.api.errors import ApiError, request_id
from pipelines.lib.retrieval import User

FAILED = "email or password not accepted"
BEARER = {"WWW-Authenticate": "Bearer"}

_dummy: str | None = None
_dummy_lock = threading.Lock()


def _dummy_hash() -> str:
    """A hash no password matches, computed once: an unknown email costs the same scrypt work as a known one."""
    global _dummy
    with _dummy_lock:
        if _dummy is None:
            _dummy = passwords.hash_password(secrets.token_urlsafe(24))
    return _dummy


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("ascii", "replace")).digest()


@dataclass(frozen=True)
class Principal:
    user: User
    token_sha256: bytes

    @property
    def employee_id(self) -> int:
        return self.user.employee_id


def _employee_id(email: str) -> int | None:
    rows = db.fetch("SELECT employee_id FROM employees WHERE lower(email) = lower(%s)", (email.strip(),))
    return int(rows[0]["employee_id"]) if rows else None


def sign_in(email: str, password: str, rid: str | None) -> tuple[str, datetime, User]:
    emp = _employee_id(email)
    with store.pool().connection() as conn:
        row = cast(Any, conn.execute("SELECT password_hash, disabled, locked_until > now() AS locked FROM logins "
                                     "WHERE employee_id = %s", (emp,)).fetchone()) if emp is not None else None
    if row is None or row["disabled"] or row["locked"]:
        passwords.verify_password(password, _dummy_hash())         # the same work as a real check
        reason = "no_login" if row is None else "disabled" if row["disabled"] else "locked"
        audit.record(employee_id=emp, resource_type="login", action="sign_in", decision="denied", request_id=rid,
                     resource_id=str(emp) if emp else None, detail={"reason": reason})
        raise ApiError(401, FAILED, slug="sign_in_failed", headers=BEARER)
    if not passwords.verify_password(password, row["password_hash"]):
        with store.pool().connection() as conn:
            n = cast(Any, conn.execute(
                "UPDATE logins SET failed_attempts = failed_attempts + 1, locked_until = CASE WHEN "
                "failed_attempts + 1 >= %s THEN now() + %s ELSE locked_until END WHERE employee_id = %s "
                "RETURNING failed_attempts", (config.MAX_FAILURES, config.LOCK_FOR, emp)).fetchone())["failed_attempts"]
        audit.record(employee_id=emp, resource_type="login", action="sign_in", decision="denied", request_id=rid,
                     resource_id=str(emp), detail={"reason": "wrong_password", "failures": n,
                                                   "locked": n >= config.MAX_FAILURES})
        raise ApiError(401, FAILED, slug="sign_in_failed", headers=BEARER)
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + config.TOKEN_TTL
    with store.pool().connection() as conn, conn.transaction():
        conn.execute("UPDATE logins SET failed_attempts = 0, locked_until = NULL WHERE employee_id = %s", (emp,))
        conn.execute("INSERT INTO tokens (token_sha256, employee_id, expires_at) VALUES (%s, %s, %s)",
                     (token_hash(token), emp, expires))
    assert emp is not None
    user = context.load_user(emp)
    audit.record(employee_id=emp, resource_type="login", action="sign_in", decision="allowed", request_id=rid,
                 resource_id=str(emp), detail={"role": user.role, "department": user.department})
    return token, expires, user


# Declares the bearer scheme in the OpenAPI schema (Frontend plan F0: the generated client knows every signed route);
# auto_error off: `principal` below keeps answering 401 with the API's own problem body.
BEARER_SCHEME = HTTPBearer(auto_error=False, description="the opaque token from POST /auth/login")


def principal(request: Request,
              _scheme: Annotated[HTTPAuthorizationCredentials | None, Depends(BEARER_SCHEME)] = None) -> Principal:
    """The FastAPI dependency of every endpoint but sign-in and `health/live`."""
    scheme, _, token = (request.headers.get("authorization") or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError(401, "a bearer token is required", slug="no_token", headers=BEARER)
    sha = token_hash(token.strip())
    with store.pool().connection() as conn:
        row = cast(Any, conn.execute(
            "SELECT t.employee_id FROM tokens t JOIN logins l USING (employee_id) WHERE t.token_sha256 = %s AND "
            "t.revoked_at IS NULL AND t.expires_at > now() AND NOT l.disabled", (sha,)).fetchone())
    if row is None:
        raise ApiError(401, "the token is not valid (expired, revoked or unknown)", slug="bad_token", headers=BEARER)
    try:
        user = context.load_user(int(row["employee_id"]))
    except PermissionError:                     # the employee row is gone
        raise ApiError(401, "the token is not valid", slug="bad_token", headers=BEARER) from None
    request.state.employee_id = user.employee_id
    return Principal(user, sha)


Signed = Annotated[Principal, Depends(principal)]       # `p: Signed` in a route = signed in, the employee known


def sign_out(p: Principal, request: Request) -> None:
    with store.pool().connection() as conn:
        conn.execute("UPDATE tokens SET revoked_at = now() WHERE token_sha256 = %s AND revoked_at IS NULL",
                     (p.token_sha256,))
    audit.record(employee_id=p.employee_id, resource_type="token", action="sign_out", decision="allowed",
                 request_id=request_id(request))
