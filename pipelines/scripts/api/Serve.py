"""Serve the PortPilot API (FastAPI plan; the app: `pipelines/api/app.py`).

Command (from the project root):
    uv run python pipelines/scripts/api/Serve.py [--port 8000]
        uvicorn on 127.0.0.1 only (plan A8, like the databases: ADR-034), one process (plan §4, owner A2: the upload
        store and the run events are per process by design); the docs at http://127.0.0.1:8000/docs
    $env:API_FAKE_ROLES = "1"; uv run python pipelines/scripts/api/Serve.py --fake-roles
        test mode for the web's end-to-end tests (Frontend plan §10.4): the real databases, a scripted model
        (`pipelines/api/fake.py`) — no model quota; refused without API_FAKE_ROLES=1, and always refused when
        PORTPILOT_ENV is staging / production (ADR-071)
    In a container (deploy/compose.yaml): PORTPILOT_ENV=staging|production and API_BIND_HOST=0.0.0.0 — the port is
        reachable on the compose network only (never published); locally the bind is always 127.0.0.1

Reads:   `.env` (the four logins, the API keys of the models and tools, `SENTRY_DSN`, `LANGSMITH_API_KEY`), the
         databases, the model APIs through llm.py (shared quota).
Writes:  checkpoints (agent_state), schema `api` (tokens, conversations, audit), reports/_log/api.jsonl (the access
         log), published packs in reports/; Sentry events and LangSmith traces when their keys are set.
Re-run:  safe; stop with Ctrl+C.
"""
import argparse
import os
import sys
from pathlib import Path

import uvicorn

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from pipelines.agents import monitoring  # noqa: E402
from pipelines.lib import environment  # noqa: E402

HOST = environment.LOOPBACK


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--fake-roles", action="store_true", help="test mode: a scripted model (needs API_FAKE_ROLES=1)")
    args = ap.parse_args()
    env = environment.name()                       # an unknown PORTPILOT_ENV stops here
    if args.fake_roles or os.environ.get("API_FAKE_ROLES") == "1":
        environment.require_local("--fake-roles / API_FAKE_ROLES")
    if args.fake_roles and os.environ.get("API_FAKE_ROLES") != "1":
        sys.exit("--fake-roles is a test mode: set API_FAKE_ROLES=1 to confirm (it never serves real answers)")
    # Sentry: errors + WARNING+ logs, the fifth entry (ADR-062 amendment 2); per-request tags on each event's own scope
    monitoring.init(entry="api", launched_by="api")
    factory = "pipelines.api.fake:create_fake_app" if args.fake_roles else "pipelines.api.app:create_app"
    host = environment.bind_host()
    print(f"PortPilot API ({env}) on {host}:{args.port}", flush=True)
    uvicorn.run(factory, factory=True, host=host, port=args.port, workers=1, proxy_headers=False,
                server_header=False, date_header=False)


if __name__ == "__main__":
    main()
