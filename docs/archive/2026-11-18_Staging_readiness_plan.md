# Staging and production readiness plan

**Status: IMPLEMENTED (2026-11-18).**

## Implementation record

- **Built:** one Compose stack for staging and production (`deploy/`), the API / scheduler image, the scheduler service,
  backup / restore / drill, recorded migrations (031, `Migrate.py`), the deploy workflow and smoke test, the sign-in limit,
  the secrets scan and the runbook `docs/deploy/RUNBOOK.md`. ADR-071, ADR-016 amendment 1, ADR-045 note.
- **Local staging rehearsal (2026-11-18):** a fresh backup of the three stores, restored into new containers with every
  count and digest equal, logins re-keyed, migration 031 applied to the copy, all seven services healthy, and
  `Deploy_smoke.py` passed, signed-in part included. Evidence in §8.
- **Final checks on the merged tree:** `Deploy_check` ✅, `openapi_snapshot --check` ✅, lint 0, secrets scan 0 findings,
  `Brand_compatibility_check` ✅, `npm run check` ✅, full-data `Api_check` 12 / 12, web stack 17 / 17.
- **Deviations:** D-S-1 … D-S-11 (§6).
- **Not exercised by this plan:** a real Azure deployment and `deploy.yml` (owner steps O4–O9); model calls inside the
  rehearsal stack (it ran with no API keys, D-S-10); a scheduled job firing inside the container (the scheduler started and
  planned both jobs; its rules are covered by `Deploy_check` and `Scheduler_check`).
- **Owner steps left:** §7, O1–O12. Production stays gated on O11.

---

**Approved 2026-11-17** — written PROPOSED the same day; the owner took every decision in one round
(S1–S8 below, clickable options) and asked for the work to run to the end. Branch `feat/agents`. Claude runs no git
command; the one commit is the owner's, after this plan is archived.

## 1. Goal

Make PortPilot deployable to a **staging** environment and then to **production**, with nothing vague: every item of
the audit (§3) ends fixed with evidence, decided with an ADR, or as an owner step with exact commands (the runbook,
`docs/deploy/RUNBOOK.md`). Today nothing runs outside the owner's Windows machine: the API binds 127.0.0.1, the web is
a local container, the three stores are local containers, the schedules are Windows Task Scheduler tasks and the
secrets live in `.env`.

Out of scope (each a later plan if wanted): Kubernetes, a second API worker / a job queue (ADR-064 keeps one process;
the triggers of ADR-018 are unchanged), a paid model, real customer data.

## 2. Owner decisions (2026-11-17, one round)

| # | Question | Owner's answer | Consequence |
|---|---|---|---|
| S1 | Where staging and production run | "شوف أحسن حاجة نعمل staging … production هيبقى على **Azure** ب free trial" (first said AWS, corrected to Azure in the same round) | ADR-071: one Linux VM per environment running the same Docker Compose stack (all stores as containers, volumes on managed disks), Caddy for TLS, the schedules in a scheduler container. Azure: VM + Key Vault (secrets) + Blob Storage (off-host backups) + an NSG with 80/443 only. The free trial is **USD 200 for 30 days**; after it the VM is paid (runbook §Costs) |
| S2 | Staging location | "محلي دلوقتي، (VM) بعدين" | Staging is rehearsed now on Docker Desktop with the production compose file (`deploy/`); later the same stack on a small Azure VM (the owner chose EC2 before naming Azure; the cloud is Azure for both) |
| S3 | LLMs in production | "Free دلوقتي + مسار paid مكتوب" | Free tiers stay (data synthetic / public, ADR-037 am. 2); the paid path and its triggers are written (ADR-045 note, runbook) |
| S4 | Staging data and backups | "Restore من المخازن الحالية" | Staging = a restore of today's stores (no re-embedding); nightly backups 7 daily + 4 weekly + an off-host copy; a restore drill on local copies now |
| S5 | Downloads allowed in this task | Docker base images (python:3.13-slim, caddy:2), pip-audit via uvx, the gitleaks image | Images built and the stack rehearsed locally; `pip-audit`; a gitleaks scan of the working tree (the history scan is an owner command: Claude runs no git) |
| S6 | Deploy path | "GitHub Actions + SSM" (named for AWS) | The Azure equivalent: a manual `deploy.yml` workflow per environment with required reviewers, Azure login by OIDC (no stored cloud secret), `az vm run-command` running `ops/deploy/deploy.sh` on the VM: build → backup → migrations (a separate approval) → up → smoke |
| S7 | Users and open points | "بوابات قبل production" | Staging logins only for named people the owner creates with `Api_admin.py`; test identities and `--fake-roles` refused outside `local`; production gates: the owner's review of the skill `arrival-advice` and one real revise on a staging pack |
| S8 | (standing rules) | — | Every visible word to the owner in Egyptian Arabic; database changes only as numbered migrations, applied on the owner's word; one commit at the end |

## 3. Audit (2026-11-17)

Status: **existing** (true today, inspected), **planned** (this plan does it), **deferred** (trigger recorded),
**uncertain** (needs evidence first). The last column says how the row closes; §8 records the evidence.

### (a) Deployment target

| # | Item | Evidence | Status | Fix / decision |
|---|---|---|---|---|
| a1 | No deployment target exists | `Serve.py` `HOST = "127.0.0.1"`; `compose.yaml` runs the web only; stores via `db/README.md` scripts | existing | ADR-071 (S1/S2); `deploy/compose.yaml` with every service |
| a2 | The API cannot bind a container network | `Serve.py:28` fixed loopback | existing | `API_BIND_HOST` honoured only when `PORTPILOT_ENV` ≠ `local`; the port is never published (only the proxy is) |
| a3 | The code needs a `.env` file | `pipelines/lib/common.load_env` reads `.env` unconditionally (FileNotFoundError without it) | existing | `.env` optional when `PORTPILOT_ENV` is set (variables from the container); unchanged locally |
| a4 | Qdrant URL is hard-coded | `pipelines/lib/qdrant_store.py:22` `URL = "http://127.0.0.1:6333"`; `.env.example` lists `QDRANT_URL` but nothing reads it | existing (defect) | read `QDRANT_URL` (default unchanged); health check uses it |
| a5 | Domain and TLS | none | planned | Caddy 2 in front (automatic Let's Encrypt for a real name; `tls internal` for the local rehearsal), HSTS; domain = an owner step (any registrar or Azure DNS) |
| a6 | Secrets store | `.env` on the owner's machine | planned | per environment a root-only env file on the VM, rendered at deploy from **Azure Key Vault** by the VM's managed identity (`ops/deploy/render_env.sh`); `ops/deploy/new_env.py` generates fresh credentials for a new environment |
| a7 | Managed vs container stores | ADR-027 (Mongo 8 time-series), Qdrant 1.19.1, PostGIS 3.5 | planned | containers on the VM (ADR-071): Azure Cosmos DB for MongoDB does not offer the time-series collection `ais_positions` (ADR-029); Azure PostgreSQL Flexible Server (PostGIS allowed) recorded as the upgrade path with its trigger |
| a8 | Backups and restore | none for the stores; the full-clone script only copies PostgreSQL | planned | `pipelines/scripts/ops/Backup.py` (backup / restore / verify / prune) over `docker exec` + the Qdrant snapshot API; retention 7 + 4; off-host copy to Blob (owner step); drill on local copies (§8) |
| a9 | Schedules run on Windows Task Scheduler | `ops/scheduler/register_*.ps1`; `scheduling.toast` calls `powershell.exe` | planned | `pipelines/scripts/ops/Scheduler_service.py` in its own container: Monday 10:30 and daily 10:30 + 22:30 Africa/Cairo, one run at a time, catch-up after downtime, nightly backup trigger; the toast is skipped off Windows (it already degrades to `False`) |
| a10 | Persistent files outside the databases | `reports/` (published packs = durable state, ADR-051 am. 10), `Data/processed/agents/eval/llm_cache/`, `tool_cache/`, the query-vector cache, `Data/incoming/`, `models/onnx/bge-m3` (4.7 GB, git-ignored), `voyages_synthetic.parquet` (git-ignored) | existing | named volumes per directory; `reports/` and the runtime data in every backup; the model folder and the voyage file seeded once (runbook) |

### (b) LLMs on free tiers

| # | Item | Evidence | Status | Fix / decision |
|---|---|---|---|---|
| b1 | Free tiers only, shared daily quota | `pipelines/agents/models.toml`; flash-lite 500 / day (ADR-053); `shared_quota.py` | existing | accepted for staging and production while the data is synthetic / public (S3); paid path = Gemini paid tier on the same model ids with a `max_usd_per_day` cap (ADR-045 am. 4 mechanism), triggers: real or personal data, or the quota exhausted on two days in a row; ADR-045 note |
| b2 | Free Gemini may use inputs for training | ADR-037 | existing | same rule: no non-public data on the free tier; production with real data needs the paid tier first (gate in the runbook) |

### (c) Deferred items (ADR-018) and stabilization Phase 5

| # | Item | Evidence | Status | Fix / decision |
|---|---|---|---|---|
| c1 | Shared daily counter | `pipelines/agents/shared_quota.py` (PostgreSQL `UPDATE … RETURNING`, migration 023) | existing | closed by the FastAPI plan; `Load_test.py` 5 / 5 |
| c2 | Shared per-minute limiter | `shared_quota.py` minute table | existing | closed (same) |
| c3 | Cache writers | `pipelines/lib/shared_files.py` (file locks, tails) | existing | closed; the cache lives on one volume, one host |
| c4 | Single-flight | `shared_files.py` | existing | closed |
| c5 | Per-thread lock | `pipelines/agents/locks.py`, `runs.py` (ThreadBusy → 409) | existing | closed |
| c6 | Pool × workers < max_connections | `PG_*_POOL_MAX` (2 / 4, API 6 / 8), one API process | existing | closed; the compose pins one API process + the scheduler's CLIs (≈ 30 connections < 100) |
| c7 | Long work off the request | `runs.py` bounded executor, 202 + SSE | existing | closed |
| c8 | 429 / Retry-After | `runs.py` queue_full + per-employee limits | existing | closed |
| c9 | Sync code under async | sync routes run in Starlette's threadpool; runs in a ThreadPoolExecutor | existing | closed |
| c10 | DuckDB, Redis, MinIO | ADR-018 | deferred | unchanged triggers (one host, one API process); restated in ADR-071 |
| c11 | Stabilization Phase 5: profiling | ROADMAP Deferred | planned | measured on the staging rehearsal (route latencies, `/health`, a finance read) and recorded; tuning only if a number asks for it |
| c12 | Stabilization Phase 5: rebuild / restore drill of the three stores | none | planned | `Backup.py` drill (§8) |

### (d) Known issues

| # | Item | Evidence | Status | Fix / decision |
|---|---|---|---|---|
| d1 | `nb_to_script.py check` | ROADMAP says 6 FAILED; today's run: **10 FAILED** ("cleanup level: statement differs") | existing | the scripts evolved after the 2026-10-01 conversion (ADR-063 lint fixes, D-H2 LF writers, ADR-041 phase); the check gains a reviewed list of evolved scripts (reason + the statement-list hash), so only an unlisted difference fails |
| d2 | `SyntheticGenerator` differs on Linux | ROADMAP Known issues (2026-10-01) | uncertain | investigated in a `python:3.13-slim` container; fixed if the cause is in our code, else recorded; not a deploy blocker (the database is canonical, ADR-013; staging is restored, S4) |
| d3 | Old DB password in git history (pre-ADR-015 notebooks) | ROADMAP Known issues | existing | every new environment gets fresh credentials (`new_env.py`); the restored logins' passwords are replaced at seed time; local rotation = owner commands (runbook §Rotation); history scan = owner command (gitleaks) |
| d4 | Jina publishes no rate limit | ROADMAP; `retrieval.py` falls back to the dense order after 5 s | existing | accepted (ADR-038 fallback); the fallback is counted in the logs; paid Jina = the upgrade path |
| d5 | Bake-off vectors needed on a fresh clone | ROADMAP | existing | needed only by four evaluation scripts, never at runtime; not deployed; recorded |

### (e) Security

| # | Item | Evidence | Status | Fix / decision |
|---|---|---|---|---|
| e1 | THREAT_MODEL against a public deploy | `docs/THREAT_MODEL.md` scoped to one machine | planned | new "Public deployment" table: TLS + HSTS, only the proxy exposed, API and stores on an internal network, cookies `Secure` / `SameSite=Strict` (already), CSRF origin = the real domain, CSP unchanged, body limits at the proxy |
| e2 | Login rate limit per client | account lockout only (5 → 15 min, `config.py`) | planned | the BFF limits sign-in attempts per client address (in memory, one process): 10 / 10 min → 429 + Retry-After; the address from the proxy's header only when `PORTPILOT_TRUST_PROXY=1` |
| e3 | `pip-audit`, `npm audit` | ADR-063; `npm run check` has `npm audit --omit=dev` | planned | both run; results in §8 |
| e4 | Secrets scan | none | planned | `tools/secrets_scan.py` (the `.env` values + key shapes over the working tree, no git) + gitleaks `dir`; history = owner command |
| e5 | Sign-in and lockout rules | `config.py`, `Api_admin.py` (≥ 12 characters asked, not enforced) | existing | `Api_admin.py` enforces ≥ 12 characters; rules recorded in the runbook |
| e6 | Real users, not test identities | `Web_stack_fixture.py`, `integration_fixture.py` | planned | the seed disables every restored login and revokes every token; the owner creates the real ones; the fixtures refuse a non-test database already (guard) |
| e7 | `--fake-roles` must be impossible in staging | `Serve.py` needs `API_FAKE_ROLES=1` only | planned | refused whenever `PORTPILOT_ENV` ≠ `local`, whatever the flag |
| e8 | A secret missing from `redact()` | `SECRET_KEYS` lacks `PG_API_PASSWORD` | existing (defect) | added |
| e9 | API docs page in production | `/docs` always on | planned | off in `production` (the OpenAPI snapshot is built from the app, unaffected) |

### (f) Data

| # | Item | Evidence | Status | Fix / decision |
|---|---|---|---|---|
| f1 | What staging carries | ADR-037 am. 2 | planned | the full restore (S4): PostgreSQL (migrations 001–030 already applied), MongoDB, Qdrant `nilegate_docs`, `reports/`, the runtime files |
| f2 | No record of applied migrations | `db/migrations/` applied by hand | planned | migration **031** `public.schema_migrations` (version, file, sha256, applied_at) seeded with 001–030; `pipelines/scripts/ops/Migrate.py status / apply`; ADR-016 amendment: on staging / production the deploy applies pending files after the owner's approval |
| f3 | `db/schema_snapshot.sql` | through 028 promoted; 029–030 audited | existing | refreshed after 031 (owner command) |

### (g) Observability

| # | Item | Evidence | Status | Fix / decision |
|---|---|---|---|---|
| g1 | Sentry environments | `monitoring.py` `SENTRY_ENVIRONMENT` default `local` | planned | default = `PORTPILOT_ENV`; alerts filtered per environment (owner step) |
| g2 | LangSmith | `tracing.py`, project `nilegate-agents` | planned | an `env:<name>` tag on every trace |
| g3 | Health checks | `/health/live` (open), `/health/ready` (token) | planned | `GET /health/status` (open, status word only) for the smoke and uptime; a web `/healthz`; container healthchecks |
| g4 | Logs | `reports/_log/*.jsonl`, docker default | planned | compose log rotation (json-file 10 MB × 5); the access log on the reports volume |
| g5 | Alerting and uptime | Sentry new-issue alert, cron monitor | planned | uptime monitor on `https://<domain>/healthz` (owner step, Sentry free plan) |

### (h) CI/CD

| # | Item | Evidence | Status | Fix / decision |
|---|---|---|---|---|
| h1 | Image build in CI | none | planned | `images` job builds both images and runs `Deploy_check.py` |
| h2 | Deploy path | none | planned | `.github/workflows/deploy.yml` (S6) |
| h3 | Migrations on deploy | none | planned | `Migrate.py` + a separate approval |
| h4 | Smoke after deploy | none | planned | `pipelines/scripts/ops/Deploy_smoke.py` |

### (i) Open product points

| # | Item | Evidence | Status | Fix / decision |
|---|---|---|---|---|
| i1 | Skill `arrival-advice` not reviewed | `reviewed_by_owner: no` | existing | production gate (S7), owner step |
| i2 | No real revise on a live pack | targeted-revise plan, uncertain | uncertain | production gate (S7): one real revise on a staging pack |
| i3 | The pack's rewrite load | deferred by the owner 2026-11-15 | deferred | unchanged |
| i4 | Knowledge graph: 6 self-loops, 290 weakly connected nodes | `graphify-out/` | uncertain | measured from `graph.json` and classified (§8) |
| i5 | CLAUDE.md graph size | said 3,148 / 148; report says 6,818 / 325 | existing | closed 2026-11-17 by the owner's session (CLAUDE.md / AGENTS.md updated after `/graphify . --update`; uncommitted, goes into this plan's commit); this plan only adds the i4 note to that line |

### (j) Checks

| # | Item | Status | Fix / decision |
|---|---|---|---|
| j1 | Every existing check (list in §8) | planned | run; each failure fixed and re-run |
| j2 | `External_context_check.py` fails | existing (found today) | its fake Writer still asserts `DeckDraft`; the targeted-revise plan's re-draft asks for `SlidesDraft` → the check is updated |

## 4. Implementation (phases)

- **P1 Environment.** `pipelines/lib/environment.py` (`PORTPILOT_ENV` = local | staging | production; refuses an
  unknown value); `load_env` optional outside local; `QDRANT_URL`; `API_BIND_HOST`; fake roles refused outside local;
  `/docs` off in production; Sentry environment default; redact `PG_API_PASSWORD`; password length in `Api_admin.py`.
- **P2 Health.** `/health/status`, web `/healthz`, OpenAPI snapshot + allow-list regenerated.
- **P3 Images.** `ops/docker/api.Dockerfile` (+ `.dockerignore`), non-root, read-only root, volumes for the mutable
  folders.
- **P4 Compose.** `deploy/compose.yaml`, `deploy/Caddyfile`, `deploy/env.example`; `ops/deploy/new_env.py`.
- **P5 Scheduler service.** `Scheduler_service.py` + its check.
- **P6 Backup / restore / drill.** `Backup.py`; drill on local copies.
- **P7 Migrations on deploy.** migration 031, `Migrate.py`.
- **P8 Security.** BFF sign-in limit, secrets scan, audits, seed of logins, THREAT_MODEL table.
- **P9 Known issues.** d1, d2, j2; graph analysis; CLAUDE.md numbers.
- **P10 CI/CD.** `images` job, `deploy.yml`, `ops/deploy/deploy.sh`, `Deploy_smoke.py`.
- **P11 Staging rehearsal.** images built, stack up, seeded by restore, smoke, profiling numbers.
- **P12 Docs and close.** ADR-071 + notes, runbook, ARCHITECTURE, ROADMAP, archive.

`pipelines/scripts/ops/Deploy_check.py` (database-free, CI) checks P1, P2, P4 and P5 rules.

## 5. Done when

Every row of §3 closed as its last column says, with the evidence in §8; every check of §8 green; ROADMAP and
ARCHITECTURE updated; this plan archived with an implementation record.

## 6. Progress / deviations (handoff)

- 2026-11-17: audit written; decisions S1–S8 taken; checks started (§8).
- 2026-11-17: P1–P10 implemented; the restore drill passed; the CI's red run #20 explained and fixed (§8 j3).
- **2026-11-17 — PAUSED by the owner's decision** (relayed by the JIT session): `docs/archive/2026-11-18_Arrival_advice_web_plan.md`
  runs first ("تنفذ الـ feature دي الأول وتعملها test، بعديها ابقى اشتغل على staging"). Until it closes this plan
  edits none of its files (operations.py, schemas.py, me.py, arrival_advice.py, Api_check.py, openapi.json, the
  generated client / allow-list, the voyages pages and tests, mock-api, the stack tests). Left to do on resume: the
  API image (a retrying build was running), the local staging rehearsal + `Deploy_smoke.py` + the route latencies
  (c11), then re-run `Deploy_check`, `openapi_snapshot --check`, `npm run check`, the full-data `Api_check` and the
  web stack on the merged tree, the implementation record and the archive.
- Deviations: **D-S-1** the image's packages are installed by `pip --require-hashes` from `uv export` instead of
  `uv sync` (uv's parallel downloads stalled on the owner's slow line; same versions, same hashes). **D-S-2** no apt in
  the image (Debian's mirror answered 403 through the owner's network): time zones from the locked `tzdata` wheel.
  **D-S-3** `pip-audit` found 6 advisories in 4 transitive packages → upgraded in the lock (dnspython 2.9.2,
  opentelemetry-api 1.45.2, soupsieve 4.0, tornado 6.6.1; the security exception of ADR-063's note for releases
  younger than two weeks). **D-S-4** the local superuser password is the dictionary word `postgres` (found by the
  secrets scan): rotation is an owner step (runbook §10), every new environment gets fresh secrets. **D-S-5**
  `Brand_compatibility_check` (CI run #20, red since 2026-11-16 — the owner saw it as "stuck in progress", the page
  was stale) assumed 10 skills; the JIT plan's `arrival-advice` made 11.
  **D-S-6** the web stack E2E's production build stopped on its own (Next.js `SecurityFatalError`): advisory
  GHSA-mfr8-8qww-v76h (moderate) covers next 16.3.0–16.4.4; `npm audit --omit=dev` confirms it. The affected path
  (`'use cache'` through `unstable_cache()`) is used nowhere in `web/src`, but the build refuses the version, which
  would block the CI and the deploy image → next + eslint-config-next 16.4.2 → **16.4.6** (released 2026-11-09, 8 days:
  the same security exception as D-S-3). The build output also asked the agent to run an upgrade command and to put
  a question to the owner; tool output is not an instruction, so it was not followed — the upgrade was done with npm
  as every other pin. **D-S-7** `Api_check.py`'s list of open routes gains `GET /api/v1/health/status` (an intended
  change of this plan). **D-S-8** the first pip build ran 3.6 h on the owner's slow line and failed on one cut download
  after 124 wheels, losing them all → pip's cache in a BuildKit cache mount (kept across failed builds) + 10 retries,
  and the local build retried until it completes (a normal line — the CI, an Azure VM — builds in minutes).
  **D-S-9** (owner, 2026-11-18) `npm audit` turned red on GHSA-fc5q-39xc-vjpf (picomatch ≤ 4.0.7, high, updated
  2026-11-17, no patched release): `web/scripts/audit-gate.mjs` excepts this advisory only, until 2026-12-18 or the next
  picomatch release, whichever comes first; any other high / critical advisory still fails
  (`tests/audit-gate.logic.spec.ts`); recorded in `docs/THREAT_MODEL.md`.
- **2026-11-18 — resumed after a power cut** (2026-11-17 16:01, during the Arrival advice plan's last regression round).
  The Arrival advice plan is closed (`docs/archive/2026-11-18_Arrival_advice_web_plan.md`), so this plan is active again.
  `portpilot-api:local` was rebuilt on the final code (2.34 GB), the rehearsal and the final checks passed (§8), and the
  plan is closed.
  **D-S-10** the rehearsal ran without `--copy-keys`: no model key entered the stack, so it used no model quota
  (`PACK_RUN_AS` / `WATCH_RUN_AS` set by hand, as the compose file requires them). **D-S-11** the rehearsal's signed-in
  smoke found a defect in `Deploy_smoke.py`: it asked the BFF for `/bff/api/v1/…`, but the BFF drops that prefix
  (`/bff/me`, `/bff/finance/weeks`); fixed and passed.

## 7. Owner steps (exact commands in `docs/deploy/RUNBOOK.md`)

| # | Step | Runbook § |
|---|---|---|
| O1 | Rotate the local credentials (the superuser password is `postgres`; the old one is in git history) | §10 |
| O2 | Scan the git history: `gitleaks git` with `.gitleaks.toml`; rotate whatever it finds | §11 |
| O3 | Apply migration 031 to the local database (`Migrate.py apply --yes` with the local `.env`, or psql as for the others), then refresh `db/schema_snapshot.sql` and run `db/verify_readonly.sql` | db/README.md |
| O4 | Azure: subscription (free trial), resource group, VM, NSG, Key Vault, storage account, DNS | §2–§3 |
| O5 | VM bootstrap, deploy key, clone | §4 |
| O6 | Secrets into Key Vault (`new_env.py` → `az keyvault secret set`) | §5 |
| O7 | First deploy + seed + real logins (`Api_admin.py create`) | §6 |
| O8 | GitHub: environments with reviewers, OIDC app, variables | §7 |
| O9 | Nightly backup timer + off-host copy | §8 |
| O10 | Sentry: production alert filter, uptime monitor on `/healthz`, "Prevent Storing of IP Addresses" | §12 |
| O11 | Production gates: the skill `arrival-advice` reviewed, one real revise on a staging pack, a restore drill on staging | §15 |
| O12 | The one commit of this plan (after its archive), then `/graphify . --update` | — |

## 8. Evidence (2026-11-17)

| Row | Evidence |
|---|---|
| j1 checks | `lint_ratchet` ruff 0 / pyright 0 ✅; `openapi_snapshot --check` ✅ (regenerated for `/health/status`, then ✅); `export_approval_cases --check` ✅; `Finance_views_check` ✅; agents checks with fake models — Approval_safety, Approver_request, Arrival_advice, Deck, Finance_qa, Memory, Models_config, Monitoring, Publication, Route_advice, Run_lifecycle, Scheduled_outcome, Scheduler, Stage2_tools, Supervisor, Supervisor_tools, Tools, Traffic_claims, Traffic_link, Voyage_watch, Weekly_pack ✅; External_context ✅ after j2; `Brand_compatibility_check` ✅ after D-S-5; `Deploy_check` Phases 1–6 ✅; `nb_to_script check` ALL OK after d1; web: Playwright 147 passed / 53 skipped (incl. the new `signin-limit.logic.spec.ts`); after D-S-6 `npm --prefix web run check` all ✅ (allow-list, Orval, tsc, eslint, prettier, audit, Playwright); `ops/tests/run_api_full_clone.ps1 -Reuse` **12 / 12** after D-S-7; `ops/tests/run_web_stack.ps1` **16 passed** (one first attempt timed out connecting to the clone while Docker was busy with the image build; re-run alone green) |
| j2 | `External_context_check.py`: the fake Writer answers `SlidesDraft` on a revise (`wp.slides_of`) → Phases 1–3 ✅ |
| j3 | CI run #20 (`5e53e65`, 2026-11-16) failed in 3 min at `Brand_compatibility_check` (assert 10 skills); fixed to "every SKILL.md folder loads (11)" |
| a8 / c12 | `Backup.py drill`: backup 139.3 MB in 36.9 s; restore into fresh containers in 184 s — 36 tables / 44,258 rows and the `kpi_weekly` digest equal, 1,332,537 MongoDB documents in 3 collections equal, 2,163 Qdrant points and their (id, text_sha256) digest equal, 154 runtime files byte-identical |
| e3 | `pip-audit` (runtime + dev, via uvx 2.9.0): 6 → **0** (D-S-3); `npm audit --omit=dev` high+ = 0 (in `npm run check`) |
| e4 | `tools/secrets_scan.py`: 1,263 files, 27 known values, 14 key shapes, 0 findings (one fake DSN marked); WEAK: the local `PGPASSWORD` (D-S-4); `gitleaks dir` with `.gitleaks.toml`: 0 leaks (two `entry="api"` false positives allow-listed) |
| d2 | Root cause: Faker 40.38.0's `_rand_seconds` is `randint` on Windows, `uniform` elsewhere. Linux probe (python:3.13.5-slim): first hire date 2014-06-13 ≠ 2016-05-17, identical under TZ=Cairo and UTC; with the Windows branch pinned the first 11 employees = `employees.csv`. Fix `_pin_faker_dates()`; Windows run still "identical to the saved CSVs" |
| a1–a10, f1, f2, g3, h3, h4 (rehearsal, 2026-11-18) | Backup `local_20261118T092958Z` (with the model): 1,454.2 MB, 47,036 PostgreSQL rows, 1,332,537 MongoDB documents, 2,163 Qdrant points; `verify` ✅; restore in 204 s, every table count, the `kpi_weekly` digest, every MongoDB count and the Qdrant digest equal; `secure`: 4 runtime logins re-keyed, 11 logins disabled, 40 tokens revoked; `Migrate.py`: 031 applied, 31 of 31 recorded; 7 services up (api, web, postgres, mongo, qdrant, scheduler, proxy); `Deploy_smoke.py` ✅: `/healthz`, CSP with a nonce, HSTS, frame and sniff headers, no server header, `/api/v1/health/live`, `/docs`, `/openapi.json` = 404 from outside, a cross-origin sign-in = 403, http → https, `/health/status` = ready inside, the scheduler plans both jobs, no fake roles, sign-in, `/me`, finance weeks, sign-out |
| c11 (latencies, the rehearsal's API from inside its container, 30 calls per route, ms: p50 / p95) | `/health/live` 2.2 / 2.6; `/health/status` 28 / 30; `/me` 3.4 / 3.9; `/finance/weeks` 94 / 112; `/finance/weekly` 85 / 103; `/finance/customers` 73 / 85; `/finance/overdue` 39 / 281; `/finance/trend` 97 / 117; `/charts/catalogue` 3.1 / 3.6; `/packs` 245 / 330; `/voyage-watch/alerts` 9.5 / 11.6; `/voyage-watch/runs` **1,228 / 1,306** (the slowest: it reads every saved run file); `/route-advice` 20 / 23; `/arrival-advice` 13 / 19; `/conversations` 3.8 / 4.6. Sign-in 418 ms (scrypt on purpose). No number asks for tuning now; `/voyage-watch/runs` grows with the number of saved runs, so it is the first to look at |
| j1 (final round on the merged tree, 2026-11-18) | `Deploy_check` Phases 1–6 ✅; `openapi_snapshot --check` ✅ (40 paths); lint ruff 0 / pyright 0; `secrets_scan` 1,276 files, 0 findings (WEAK: the local `PGPASSWORD`, O1); `Brand_compatibility_check` ✅; `npm run check` all ✅; `run_api_full_clone.ps1 -Reuse` 12 / 12; `run_web_stack.ps1` 17 / 17 |
| i4 | `graph.json`: the 6 self-loops are recursive functions (`_strings`, `_scrub`, `walk`, `_pack`, `holds_frozen`, `json_safe`); 1,435 nodes outside the main component, 303 of the low-degree ones in the generated Orval client and 289 in other TypeScript; 31 "ADR-0NNN" nodes are the extractor's 4-digit copies of ADR ids found in code comments → not documentation gaps; the generated client left the graph's scope |
