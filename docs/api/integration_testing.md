# Isolated API integration

Stabilization R10, 2026-11-12. The deterministic suite is
`dev/checks/api/Api_integration_check.py`. The `api-integration` CI job starts a fresh PostgreSQL 16.9
service on port 55432, database `portpilot_api_test`. It needs no project `.env`, model key, loaded finance data,
MongoDB or Qdrant. Runtime roles have separate random credentials and the real migration 023 grants.

The owner can run the same check from PowerShell at the project root:

```powershell
powershell -NoProfile -File .\ops\tests\run_api_integration.ps1
```

The wrapper requires Docker Desktop and the existing locked Python environment. It refuses an existing
`portpilot-api-test` container or occupied port 55432, generates a temporary password, starts the test container,
waits for readiness, and runs through `dev/tools/run.py`. It restores environment variables on exit and retains the
container for inspection. It never stops, deletes, or connects to the application's containers. A fresh container
is required for another run: inspect the previous one before removing **only** `portpilot-api-test`.

Owner validation **passed 2026-11-12**: phases 0–4 and `Final Checkpoint: 5 / 5`, exit 0 in 64s. The saved
validation log was inspected; durable evidence is `dev/db_audit/postgres/2026-11-12_api_integration_report.txt`. This verifies
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
uv run python dev/checks/api/Api_integration_check.py --guard-only
```

`Api_check.py`, the historical full-store suite, now refuses implicit/live PostgreSQL targets and creates its own
seven fixture employees instead of searching for employees without logins. It requires an owner-prepared full-data
clone at `127.0.0.1:55432/portpilot_api_test`, `PORTPILOT_API_TEST_DSN`, explicit matching `PGHOST`, `PGPORT`,
`PGDATABASE`, and `PORTPILOT_FULL_STACK_ISOLATED=1`. All API/read/agent credentials must work on that clone; the
full suite also needs its other store/model fixtures. The thin CI fixture is deliberately insufficient for it.
Full-clone preparation is scripted (2026-11-15): `powershell -NoProfile -File .\ops\tests\run_api_full_clone.ps1`
starts a new container `portpilot-api-full` (the image of `ports-postgres`) on 127.0.0.1:55432, copies the logins
(password hashes, without `postgres`) and the whole `ports_logistics` as `portpilot_api_test` (ports-postgres is only
read), then runs `Api_check.py` with every runtime pool pointed at the clone; execution is the owner's. First full run 2026-11-15: 12 / 12 phases (`-Reuse` re-runs it on the same clone). Never point it
at the application database. Normal cleanup
removes only its dedicated employees/logins/conversations/threads and test audit rows in the isolated database.

## The web over the real API (local-stack E2E)

Frontend plan §10.4, 2026-11-16. `web/playwright.stack.config.ts` runs the Playwright suite `web/tests/stack/`
(`*.stack.spec.ts`, outside CI and outside `npm run check`) against the real API in its test mode
(`Serve.py --fake-roles --port 8011`: a scripted model, no LLM quota, Sentry and LangSmith off) over the same
full-data clone `portpilot-api-full`, and a production build of the web on port 3101. The owner runs it with:

```powershell
powershell -NoProfile -File .\ops\tests\run_web_stack.ps1
```

The config refuses to start unless the clone's variables are set (the runner sets them from the container). Global
setup / teardown call `dev/checks/api/Web_stack_fixture.py setup | cleanup`: eight employees 910001–910008
(`web-stack-N@nilegate.com`, random passwords in the git-ignored `web/tests/stack/.fixture/people.json`) and,
afterwards, everything they made (conversations, tokens, audit rows, `ask:` / `route_advice:` threads). Coverage:
the access matrix of the seven profiles (menu, pages, BFF reads of finance and packs; another employee's
conversation and answer refused — the CEO reads them, as designed), sign-in messages, the silent lockout, sign-out,
a follow-up resolved by code, a refused tool, the real upload screening (`clean_D1.pdf` accepted,
`inj_metadata_block.pdf` refused), route advice without the canal, the voyage watch. First run: 15 / 15 (3.3 min).
