"""The API's settings (FastAPI plan §6, §9, A7 / A8): fixed values here, the few that vary per machine from `.env`."""
import os
from datetime import timedelta

from pipelines.lib.common import load_env

TOKEN_TTL = timedelta(hours=8)
MAX_FAILURES = 5                       # wrong passwords in a row → the login is locked …
LOCK_FOR = timedelta(minutes=15)       # … for this long
MAX_BODY_BYTES = 16 * 1024             # every JSON body
UPLOAD_MAX_BYTES = 5 * 1024 * 1024     # the upload route only (ADR-042's limit), P5
QUESTION_MAX_CHARS = 2000
DEFAULT_CORS_ORIGIN = "http://localhost:3000"


def cors_origins() -> list[str]:
    """`API_CORS_ORIGINS` (comma-separated) or the frontend's dev origin; never `*` (plan §9)."""
    load_env()
    raw = os.environ.get("API_CORS_ORIGINS") or DEFAULT_CORS_ORIGIN
    origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    if "*" in origins:
        raise ValueError("API_CORS_ORIGINS may not be '*': list the UI's origin(s)")
    return origins
