# Isolated API integration

Stabilization R10, 2026-11-12. The deterministic suite is
`pipelines/scripts/api/Api_integration_check.py`. The `api-integration` CI job starts a fresh PostgreSQL 16.9
service on port 55432, database `portpilot_api_test`. It needs no project `.env`, model key, loaded finance data,
MongoDB or Qdrant. Runtime roles have separate random credentials and the real migration 023 grants.

The owner can run the same check from PowerShell at the project root:

```powershell
powershell -NoProfile -File .\ops\tests\run_api_integration.ps1
```

The wrapper requires Docker Desktop and the existing locked Python environment. It refuses an existing
`portpilot-api-test` container or occupied port 55432, generates a temporary password, starts the test container,
waits for readiness, and runs through `tools/run.py`. It restores environment variables on exit and retains the
container for inspection. It never stops, deletes, or connects to the application's containers. A fresh container
is required for another run: inspect the previous one before removing **only** `portpilot-api-test`.

Owner validation **passed 2026-11-12**: phases 0–4 and `Final Checkpoint: 5 / 5`, exit 0 in 64s. The saved
validation log was inspected; durable evidence is `db/audit/2026-11-12_api_integration_report.txt`. This verifies
the disposable PostgreSQL suite. Pushed CI and full-data application acceptance remain separate pending gates.

The fixture uses seven new employee IDs 900001–900007 and generated passwords. The employee table definition is
read from the schema snapshot, including its retained `nilegate.com` constraint. API tables/grants come from
migration 023 (only its database CONNECT grant is retargeted); approved-publication tables come from migration
024. Minimal roles/departments are fixture data. No application migration or schema snapshot is changed.

Coverage: seven login profiles, hashed tokens, owner/CEO conversation access, least-privilege SQL denials,
owned run GET/SSE replay, logout revocation, locks on independent PostgreSQL connections, and rollback/retry of
the real `store_approved` transaction. Graph/model behavior remains covered by separate deterministic checks.
Finance views, full deck generation, PostGIS, MongoDB/Qdrant, providers and Power BI parity remain full-data gates.

For a quick database-free guard check:

```powershell
uv run python pipelines/scripts/api/Api_integration_check.py --guard-only
```

`Api_check.py`, the historical full-store suite, now refuses implicit/live PostgreSQL targets and creates its own
seven fixture employees instead of searching for employees without logins. It requires an owner-prepared full-data
clone at `127.0.0.1:55432/portpilot_api_test`, `PORTPILOT_API_TEST_DSN`, explicit matching `PGHOST`, `PGPORT`,
`PGDATABASE`, and `PORTPILOT_FULL_STACK_ISOLATED=1`. All API/read/agent credentials must work on that clone; the
full suite also needs its other store/model fixtures. The thin CI fixture is deliberately insufficient for it.
Full-clone preparation and execution remain pending; do not point it at the application database. Normal cleanup
removes only its dedicated employees/logins/conversations/threads and test audit rows in the isolated database.
