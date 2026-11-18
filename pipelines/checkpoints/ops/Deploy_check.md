# Deploy_check — Final Checkpoint (Staging readiness plan, ADR-071)

`pipelines/scripts/ops/Deploy_check.py` proves the deployment's rules with no database, no network and no Docker, so
it runs in the CI `checks` job and on the owner's machine.

| Phase | What it checks | Result (2026-11-17) |
|---|---|---|
| 1 | `PORTPILOT_ENV`: unknown names stop; loopback bind locally, `API_BIND_HOST` outside; `.env` optional only outside local; `Serve.py --fake-roles` and `fake.create_fake_app()` refused in staging / production; CORS https-only outside local; `/docs` and `/redoc` 404 in production, 200 in staging; `/health/status` in the schema; `redact()` knows `PG_API_PASSWORD` / `SENTRY_DSN` | ✅ |
| 2 | `deploy/compose.yaml`: 8 services; only the proxy (and Qdrant on the host loopback) publish ports; `backend` internal; no `env_file`; the database owner's password only in `postgres` / `ops`; no model key in a store; the web's three variables; read-only roots, `cap_drop: ALL`, `no-new-privileges`, pinned images, log rotation; every required variable in `deploy/env.example`; the Caddyfile hides the API, sets HSTS and a 6 MB limit | ✅ |
| 3 | `ops/docker/api.Dockerfile`: non-root, locked runtime packages, no apt; its dockerignore keeps out `.env`, raw data, caches, models; the web image runs as `node` | ✅ |
| 4 | `Scheduler_service.py`: Monday 10:30 / daily 10:30 + 22:30 Africa/Cairo (summer time included), nothing on the first start, catch-up inside 12 h / 6 h then skip, one job at a time, state kept | ✅ |
| 5 | migrations 001–031 numbered without a gap; 031's recorded hashes = the files' text (CRLF read as LF) | ✅ |
| 6 | env files read the same everywhere; backup retention 7 daily + 4 weekly (40 folders → 9); `new_env.py` writes 9 fresh, distinct secrets, none from the owner's `.env` | ✅ |

Problems met while building it: `app.routes` lists included routers lazily (Phase 1 reads the app through a
`TestClient` and `app.openapi()` instead); the dockerignore starts with comment lines (the rule list skips them);
`new_env.py` printed a path relative to the project for a temporary file (it now prints any path).
