"""Which environment this process serves (Staging readiness plan P1, ADR-071): `PORTPILOT_ENV` = local | staging |
production. Unset = `local`, the owner's machine, where everything behaves as before this plan.

What the name changes (and nothing else):
- `.env` is optional outside `local`: a container gets its variables from the compose env file, not from a file in
  the image (`pipelines.lib.common.load_env`).
- test modes are refused outside `local`: `Serve.py --fake-roles` and anything else that asks `require_local()`.
- the API may bind a non-loopback address (`API_BIND_HOST`) only outside `local` — inside a container network whose
  port is never published (only the proxy is, `deploy/compose.yaml`).
- the interactive API docs (`/docs`, `/redoc`) are off in `production`.
- Sentry's environment and LangSmith's `env:` tag default to the name.
"""
import os

ENVIRONMENTS = ("local", "staging", "production")
LOOPBACK = "127.0.0.1"


def name() -> str:
    """The environment's name; an unknown value stops the process (a typo must not fall back to `local`)."""
    value = os.environ.get("PORTPILOT_ENV", "").strip().lower() or "local"
    if value not in ENVIRONMENTS:
        raise RuntimeError(f"PORTPILOT_ENV={value!r} is not one of {', '.join(ENVIRONMENTS)}")
    return value


def is_local() -> bool:
    return name() == "local"


def require_local(what: str) -> None:
    """Refuse a test-only mode outside the owner's machine, whatever flag or variable asked for it."""
    env = name()
    if env != "local":
        raise SystemExit(f"{what} is a test mode and is refused in PORTPILOT_ENV={env}")


def bind_host() -> str:
    """The API's listen address: always the loopback locally; `API_BIND_HOST` (e.g. 0.0.0.0 inside a container) only
    in staging / production."""
    if is_local():
        return LOOPBACK
    return os.environ.get("API_BIND_HOST", "").strip() or LOOPBACK


def docs_enabled() -> bool:
    return name() != "production"
