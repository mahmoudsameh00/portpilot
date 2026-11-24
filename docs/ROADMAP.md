# Roadmap & status

Single place for project status. Current update: **2026-11-23** (see Current phase).

Historical summary last updated: 2026-11-07 (**approver-request plan CLOSED** — the manager's request in words, live on W15; migration 024, Power BI Approved Pack, ADR-067; to commit; 2026-11-06: **approver-additions plan implemented** — the owner's steps open: Power BI visuals, the live pack of 2026-11-09, one commit; frontend plan APPROVED in parallel; 2026-11-05: **FastAPI plan CLOSED** — `dev/history/archive/2026-11-05_FastAPI_plan.md`, ADR-064 / ADR-065; Stage 2 walk-through `dev/history/CHECKPOINT_agents_stage2.md`; next: the approver's note in the weekly pack, then the frontend plan; 2026-11-03: **weekly-pack improvement CLOSED** — implementation record in `dev/history/analysis/financial_intelligence/implementation_roadmap.md`, no-regression re-run D-RR-1; next: FastAPI plan; 2026-11-02: **Observability plan CLOSED** — first real Sentry check-in ok, `dev/history/archive/2026-11-02_Observability_Sentry_plan.md`; **dependency upgrade DONE** — audit 63 → 0, `dev/history/archive/2026-11-02_Dependency_upgrade_plan.md`; weekly-pack Phases B–D in place, c5 scheduled 2026-11-03 09:30; 2026-11-01: **Agents plan CLOSED and archived** — `dev/history/archive/2026-11-01_Agents_plan.md`: Stage 1 candidate c4 kept, D7 `planted_all` met (D-C4-1); active plan `docs/plans/Observability_Sentry_plan.md`, Sentry S1 done on the checks, ADR-062; 2026-10-30: Agents plan Phase 12 — the supervisor — done: Stage 2 done-when MET, baseline `stage2_eval_2026-10-30_c1.json`, ADR-059 + ADR-045 amendment 3; D-P12-7 scheduled 2026-10-31, then the one Stage 2 commit; 2026-10-29: voyage-watch task registered; D-P11-2 weather pacing after the first firing; Agents plan Phase 11 CLOSED: the `voyage_watch` graph, ADR-058, autonomous session — owner reviewed and approved 2026-10-29; Phase 12 design §6d APPROVED 2026-10-29; Phase 10 CLOSED 2026-10-27: `route_advice`, ADR-057; Phase 9 CLOSED 2026-10-27: Stage 2 tools, ADR-055 / ADR-056; Agents plan §5f Phases 7–8 closure DONE: final Stage 1 baseline `stage1_eval_2026-10-23_confirm.json`, D7 not met on planted findings only; new fallback ADR-045 amendment 2; Phase 8 CLOSED: scheduled weekly pack, retention, LangSmith, ADR-054; Phase 7 CLOSED: evaluation, finance Q&A agent, migration 017, ADR-052 / ADR-053, D7 not met — owner decision; Phase 6 CLOSED: the PortPilot PPTX, number slots, Validator v2 + V8, ADR-051; Phase 5 CLOSED: the `weekly_pack` workflow + PostgresSaver + approval, ADR-050, migration 016, ADR-045 amendment 1; Phase 4 CLOSED: Stage 1 tools + skills, ADR-049; Phase 3 CLOSED 2026-10-15: Power BI dashboard, ADR-048; Phase 2 closed 2026-10-14, ADR-047; Phase 1 closed 2026-10-14, ADR-046; Phase 0 closed 2026-10-12, ADR-045).
Labels: `DONE`, `IN PROGRESS`, `PARTIAL`, `NEXT`, `PLANNED`, `PROPOSED`, `DEFERRED`, `BLOCKED`.

## Current phase

**2026-11-23 — staging candidate.** The Operations web test exercised catch-up and just-in-time advice at the
pilot boarding place. It exposed two distinctions the writer must preserve: a rounded-speed ETA can miss the
planning target while meeting the port deadline, and planned waiting ends at the target. The fixes and verification
are recorded in the Azure staging plan, §7. Azure provisioning starts after the owner's A0 budget and access checks.

Voyage Watch now shows arrival advice only for vessels with a timing alert. The signed-in replay returned a result
for all 41 eligible vessels on the 219-row board. Three high weather alerts without a requested time had no speed
action. Late decisions use the earliest achievable arrival, and the brief's internal data stays off the web.
The fresh eight-case writer evaluation accepted six, the Arabic supervisor answered, and the watch brief passed.
The English supervisor response failed validation. The owner accepted the earlier baseline for staging.

**Update 2026-11-22 — readiness audit before Azure; the skill `arrival-advice` reviewed (D-AZ-4).** The owner chose
"edits + the risk's direction": the skill's text fixed and a direction rule in the arrival Validator (a storm → an
earlier arrival, never the Cape; a Suez drop → the Cape only), `reviewed_by_owner: 2026-11-22`, ADR-070 note;
`Arrival_advice_check.py` Phases 1–7 ✅, two real runs 7 / 8 (Gemini overloaded, the fallback model) and 8 / 8. The
readiness audit recorded 16 / 16 CI checks, 7 / 7 web checks, passing full-data checks and a local staging rehearsal on a restore of today's stores (smoke 15 / 15). Stale labels fixed in
ARCHITECTURE, this file, THREAT_MODEL and RUNBOOK §15. The owner's fresh retry scored 6 / 8 (two evidence failures).
The owner accepted the earlier results for staging if this retry fell short. The revised release order is a live
web test, then the staging candidate on remote `master` for CI. The release tag remains at A6. Frontend Sentry is
deferred until before production. The repository is now public
(verified 2026-11-22), so the A8 reviewer setup is available. A local fix checks push CI for the release SHA and
deploys that same SHA. All seven phases of `Deploy_check.py` passed. **Next:** finish owner checks in Phase A0.

**Update 2026-11-21 — one public environment (ADR-071 amendment 1); no plan is open.** The public link for testers
is the `staging` VM on Azure, and `production` is deferred until there are real users or real data. The local
Compose rehearsal is the step before each staging deploy. The checks on `master` after the first Dependabot merges
are green: the CI checks 16 / 16, web static 6 / 6, Playwright 142 passed / 58 skipped, `Stage2_tools_check`
(pymongo 4.20) and `Finance_views_check` (still pandas 3.0.5). Runbook §3 corrected: the owner's "Key Vault
Secrets Officer" role and `az storage container-rm create`. The tester guide "Try PortPilot" is the owner's private
artifact, shared from its Share menu.
**Later the same day — the Dependabot batch done (ADR-063 note of 2026-11-21).** `d54f8fa` (the voyage_watch fix,
the #17 preparation, ADR-071 amendment 1, runbook §3), then merged one by one with green checks: pandas 3.1.1 (#24,
replacing #8), pyarrow 26.0.1 (#15), @assistant-ui/react 0.15.32 (#23), faker 40.54.0 (#25), @xyflow/react 12.12.1
(#21); @types/node 25 (#22) closed with the major ignored. On `master` `6edb4a9`: CI green; locally the CI checks
16 / 16, the web check 7 / 7 including Playwright, `Finance_views_check` on pandas 3.1.1 and `Stage2_tools_check` on
pymongo 4.20 green on the full data. Dependabot is now monthly, grouped, with majors ignored and a 14-day cooldown;
`.gitattributes` keeps `web/**` LF.
**Open:** #19 onnxruntime 1.32.0 (14 days old on 2026-11-27; also the local upload check with bge-m3) and #20
langsmith 0.15.0 (2026-12-01; also one real traced run in `nilegate-agents`). They may close and come back in the
first monthly group. @xyflow/react 13: the padding is ready (`RunGraph.tsx`), the major waits for a planned task.
**NEXT (owner):** the staging deployment O4–O10 (`docs/deploy/RUNBOOK.md`, staging names and sizes) and one login per
tester. The owner approved the staging plan on 2026-11-22 and keeps the working copy locally.

**Update 2026-11-19 — Repository layout CLOSED; no plan is open** (`dev/history/archive/2026-11-19_Repo_layout_and_hygiene_plan.md`,
ADR-072; owner decisions D-RL-1…4 in one round). The runtime stays where it was (`pipelines/`, `db/`, `deploy/`,
`ops/`, `web/`, `powerbi/`, `Data/`); every check, evaluation, data builder, the run tooling, the checkpoints, the
saved audits and the history moved under `dev/` (`dev/README.md`, the map `dev/tools/layout_map.json`). The API image
no longer carries a check or builder script. New CI step `dev/tools/path_refs_check.py`: every repository path written
in a file exists, and no local tool name appears in a tracked file. The web's sample-data concept pages left the
production build. `.gitignore` reviewed; local tool and editor files are untracked (listed in `.git/info/exclude`).
Every check that ran before the move gives the same ✅ lines after it (the plan's §8 table).
The plan's §9 owner steps are done (2026-11-19 / 20): backups (two bundles, a GitHub mirror, the local tool files),
the layout commit, the history rewritten with `git filter-repo` (77 commits; no local tool file in any commit, no tool
name in any message), the repository renamed `portpilot` with an SSH remote, description and topics, `feat/agents`
merged into `master` as PR 9 after the CI fix D-RL-8, the two old merged branches deleted. `master` protection was
refused by GitHub (a private repository on a free plan: 403) and is skipped. Commit ids written in this file before
2026-11-19 (e.g. `5e53e65`, `e789453`) refer to the history before the rewrite; the owner's commit map (old → new)
and the backup bundle keep them.
**NEXT (owner):** the open Dependabot PRs (three major web updates among them) reviewed one by one; then the Azure
deployment (O4–O10, `docs/deploy/RUNBOOK.md`).

**Update 2026-11-18 — Staging readiness CLOSED; no plan is open** (`dev/history/archive/2026-11-18_Staging_readiness_plan.md`,
ADR-071). The local staging rehearsal passed on a restore of today's stores, and every check is green on the merged tree.
Done by the owner 2026-11-18: migration 031 on the local database (31 of 31 recorded, audit 0 errors) and a new local
PostgreSQL superuser password (secrets scan: 0 findings, no weak password), the one commit of this work, and the gitleaks
scan of the git history (O2: 70 commits, no leaks found).
**NEXT (owner):** the Azure deployment (O4–O10), with exact commands in `docs/deploy/RUNBOOK.md`. Production stays gated on the review of the skill `arrival-advice`, one real
revise on a staging pack and a restore drill on staging.

**Update 2026-11-18 — Arrival advice in the web CLOSED** (`dev/history/archive/2026-11-18_Arrival_advice_web_plan.md`, ADR-070
amendments 1 and 2). The watch advises every `jit` / `rta_late` vessel in its run; Voyages shows the advice under its
alert and on demand for any vessel at sea; `POST / GET /arrival-advice`. For the supervisor, a run with many arrival
alerts is folded (the largest broad request 6,990 input tokens) and fleet-wide berth / JIT questions reach the watch.
Stage 2 on the real models: every gate met, ADR-052 tie with c1 (`stage2_eval_2026-11-18_fold1.json`).
**Open (owner):** the time-limited npm audit exception for picomatch ends on 2026-12-18 (`docs/THREAT_MODEL.md`).

**Update 2026-11-17 — Staging readiness plan** (`dev/history/archive/2026-11-18_Staging_readiness_plan.md`, owner decisions S1–S8 in one
round: production on **Azure** (free trial), staging rehearsed locally now and on a VM later, free models with a
written paid path, staging seeded by a restore, deploys from GitHub Actions, production gates). ADR-071 (one Linux VM
per environment, one Compose stack, Caddy TLS, the schedules in a container), ADR-016 amendment 1 (migrations recorded
by 031, applied by the deploy on approval), ADR-045 note. Runbook `docs/deploy/RUNBOOK.md`. Status and evidence: the
plan's §8 (moved to the archive at its close).

**Update 2026-11-16 — web dashboards and reports plan CLOSED; no plan is open**
(`dev/history/archive/2026-11-16_Web_dashboards_and_reports_plan.md`).
- **Parity (Phase 5):** done on **W17**, the last published pack. Power BI's measures, read by DAX on the open Desktop
  model, = the `finance` views = the API's rows on 249 values, with 0 differences. The Dashboards page over the real
  API shows them rounded only: new stack test `web/tests/stack/parity.stack.spec.ts`, and `run_web_stack.ps1` passes
  16 / 16 (ADR-047 note, ADR-069 closing note).
- **Earlier the same day:**
  - The Reports report-week marker.
  - W17 tested from the web, then approved and published.
  - Three V9 rules (ADR-051 amendment 13).
  - The ask-back answer box.
  - Revise merged into Request.
- **`docs/plans/` is empty.**
- **Open (owner):**
  - The single commit of everything on `feat/agents`.
  - The review of the skill `arrival-advice`.
  - The W18 pack: approved and published by the owner from the web (2026-11-16, `reports/2025-W18/_publications/47d05788c12c43e39e4f0b29b6735db3`).
  - The stabilization plan's Phase 5 (optimisation) stays DEFERRED.

**Update 2026-11-16 — frontend plan and stabilization plan CLOSED** (`dev/history/archive/2026-11-16_Frontend_plan.md`,
`dev/history/archive/2026-11-16_Project_validation_and_continuation_plan.md`; owner: "أيوه، اقفلهم").
- **The frontend's done-when, all met:**
  - W17 was decided through the UI.
  - EN + Egyptian Arabic follow-ups pass on the real models, after seven memory / language fixes (ADR-065 note).
  - Power BI parity holds for W16, and the CI `web` job is green.
  - The new **local-stack E2E passes 15 / 15 with leakage 0**. It runs the web over the real API in test mode on the
    full-data clone (`web/tests/stack/`, `dev/tests/run_web_stack.ps1`; ADR-060 closing note, ADR-064 note).
- **Found the same day and fixed:**
  - "New conversation" on `/ask`.
  - The anchored-vessels question: `watch_alerts(anchored=true)`, ADR-059 note.
  - Five pre-021 packs (W08, W10–W13) that answered 500.
- **The stabilization plan:** R1–R10 are verified and every owner gate is met. Its Phase 5 (optimisation) is
  **DEFERRED** (Missing work).
- **Open:**
  - `docs/plans/Web_dashboards_and_reports_plan.md` (closed the same day, above).
  - Then the owner's single commit.
  - The owner's review of the skill `arrival-advice`.
  - The W18 pack: approved and published by the owner from the web (2026-11-16, `reports/2025-W18/_publications/47d05788c12c43e39e4f0b29b6735db3`).

**Update 2026-11-16 — targeted-revise plan CLOSED** (`dev/history/archive/2026-11-16_Targeted_revise_plan.md`, run in a
side session from the W17 session; owner decisions T1–T4): a revise re-drafts only the related slides (slide 2, the
changed note's own slide, every slide citing the same evidence; one `SlidesDraft` call; other slides, the approver's
additions and chart choices kept; edits replaced on re-drafted slides; the Validator still checks the whole deck —
ADR-050 amendment 5). Fallbacks made rare in code (tile-repeat comments dropped before the Validator, the V7
later-clause total false alarm fixed), and what code wrote or removed is shown inline on `/packs` instead of the two
banners (ADR-051 amendment 14). Checks: `Deck_check` 9 / 9, `Weekly_pack_check` 10 / 11 (Phase 5 real models
skipped), `Api_check` 12 / 12, `Approver_request_check`, lint 0, `npm --prefix web run check` ✅. Real run `tr1` vs
ec2 **"tie: keep"** (ADR-052 ninth use): every gate, narrative recall 0.931, **degraded packs 22 / 22 → 6 / 22**,
rewrites 44 → 37; baselines unchanged. **Open (owner):** the commit once every plan in `docs/plans/` is closed;
; uncertain: no real revise on a live pack yet.

**Update 2026-11-15 — JIT arrival plan CLOSED** (`dev/history/archive/2026-11-15_JIT_arrival_plan.md`, ADR-070; run in its
own session on the owner's word): Just-in-Time arrival advice, a third Operations product. The RTA is a port-call
message — `public.port_call_messages` (migration 030, applied and audited, §29; 680 synthetic messages from each
voyage's declared schedule by `Port_call_generator.py`; real messages later are new rows, no code change) — or given
in the question. `tools/arrival.py` computes keep / jit / floor / catch_up / cape; the graph `arrival_advice` (one
`writer` call with slots, a code Validator), the CLI `Arrival_advice.py`, the supervisor's tool `arrival_advice`
(JIT words only: 0 of the 57 golden items re-routed), and `rta_late` / `jit` alerts in the voyage watch (41 at the
clock). `Arrival_advice_check.py` Phases 1–8 ✅ (real model: 8 / 8 advices pass the Validator, = the rule; two supervisor questions EN + AR answered; the watch brief ok; D-J8 sign / RTA-label rules from the first real run). Regressions: `Supervisor_check`, `Supervisor_tools_check`
(union 15), `Stage2_eval` Phases 1–3, `Stage2_tools_check`, `Tools_check`, `Scheduler_check`, `Voyage_watch_check`
(fixtures and the live counts updated, D-J7), `Route_advice_check`, lint ratchet 0. No CO₂ (owner). **Open (owner):** the
review of the skill `arrival-advice` (`reviewed_by_owner: no`); the commit once every plan in `docs/plans/` is closed;
.

**Update 2026-11-15 — web dashboards and reports** (`docs/plans/Web_dashboards_and_reports_plan.md`, APPROVED the
same day, ADR-069): migration 029 (`finance.kpi_weekly_breakdown`, M18) applied and checked (`Finance_views_check`
Phase 8 ✅); the API's breakdown + Excel export (audit row per export; `openpyxl==3.1.5`); the web's five week pages
gained Power BI's missing visuals, "Break down by" + measure + compare week, and "Export to Excel"; the Reports page
has one decision bar for the whole pack; the tabs read Reports / Dashboards. `npm run check` all ✅. **Open (owner):**
Power BI parity on week 16 (Desktop + API running), the full-data `Api_check`, the commit. Same day: pushed CI on
`feat/agents` green (run 43690050303: checks, web with Playwright 130 / 50 skipped, api-integration) — the
stabilization and frontend plans' "pushed CI" gates are met; `Stage1_eval.py` records `degraded` per pack.
**Deferred by the owner (2026-11-15):** (the JIT plan — closed later the same day, above); the weekly pack's rewrite load (two Writer rewrites per pack, mostly V9) — not planned now (partly addressed 2026-11-16 by the targeted-revise plan above: rewrites 44 → 37, fallbacks 22 → 6 of 22; the rest stays deferred).
**Closed the same day: the Model flexibility plan** (`dev/history/archive/2026-11-15_Model_flexibility_plan.md`, ADR-045
amendment 4): the model per role lives in `pipelines/agents/models.toml` (swap procedure `docs/model_swap.md`, probe
`Model_probe.py`); models unchanged, cache keys byte-equal, no-regression by replays with 0 fresh calls.
**Next:** the owner's commit; Power BI parity of the web dashboards (week 16) and the full-data `Api_check` (owner
gates); then the deferred JIT plan when the owner decides.

**Closed 2026-11-14: the traffic-billing link plan**, archived as
`dev/history/archive/2026-11-14_Traffic_billing_link_plan.md` (implementation record at its top). The last acceptance
item, the live pack, is done: the stale attempts `W16:3` / `W16:4` were rejected, `weekly_pack:live:2025-W16:5`
ran on the committed tree (Validator passed; degraded — three bullets dropped by code; 3 Gemini calls + 2
fallback rewrites), the owner approved it through the web UI, and the publication is verified
(`reports/2025-W16/_publications/9f145f3119d44e6a903736a7c6913ba7/`, hashes = `publication.json`, `traffic_link`
= `no_link`, database sync `synced`). ADR-051 amendment 11, ADR-052 seventh use, notes on ADR-059 and ADR-068.
**Open (owner):** the commit of the close. **Follow-up closed the same day**
(`dev/history/archive/2026-11-14_Slide9_link_bullet_plan.md`, ADR-051 amendment 12, ADR-052 eighth use): the Writer's
slide-9 bullet on `context.link` is dropped by code before the Validator; real run `s9` = "tie: keep" vs ec2
(22 / 22 published, planted 6 / 6, recall 0.9655, 0 fallbacks); patch fixes about the link 11 → 0, rewrites
still two per pack (the patches' other problems, not planned).
**Next:** `docs/plans/Model_flexibility_plan.md` (APPROVED 2026-11-13) starts after the commit; the stabilization
plan's owner gates (full-data `Api_check`, Power BI parity, pushed CI) and the frontend / JIT plans stay as they
are. The 2026-11-14 checkpoint text below is kept as written (its "Open: the live pack" is now closed).

**Update 2026-11-14 — Git checkpoint point.** Traffic-link Phase 6 measured on the real models
(now `dev/history/archive/2026-11-14_Traffic_billing_link_plan.md`, D-TL-10 … D-TL-15): packs `tl2` = ADR-052 "keep (better)" vs ec2
(22 / 22 published, planted 6 / 6, narrative recall 0.9828); finance Q&A `tl3qa` = "tie" vs dp127b (EN / AR 1.0);
the supervisor's Stage 2 run `tl3s2` meets its done-when and is closed on it, c1 stays the baseline (EN 0.9448
vs 0.9816 from answers that omit one asked element). Fixed on the way: three scripts without the project-root
import line, the evaluation's frozen-name comparison after the rename, the notes-stage traffic claim guard (a
refused sentence is repaired, not fatal), two scorer rules, the former company name in the Q&A briefs, the
citation-page rule, the route-thread guard on in-memory savers, two slot-form rules for the supervisor.
Every database-free CI check, the database-backed tool / context checks and the web static suite pass on this
tree; API and web are not running (the machine restarted). **Open:** the live pack (owner), then the plan's
implementation record, ADRs and archive; the stabilization plan's owner gates (full-data `Api_check`, Power BI
parity, pushed CI); `docs/plans/Model_flexibility_plan.md` (APPROVED 2026-11-13) starts after the commit.
The dated text below is the state of 2026-11-12 and is kept as written.

**IN PROGRESS 2026-11-12: engineering stabilization** — approved
`dev/history/archive/2026-11-16_Project_validation_and_continuation_plan.md`. R1–R4 execution/approval repairs are implemented;
R5/R6 shared EN/AR traffic-claim enforcement is implemented and deterministically verified. R8 scheduled
business-failure reporting and R9 immutable publication/reconciliation are now implemented with offline fault
tests and visible API/web sync status (`docs/publication_recovery.md`). R7 disconnect and reload/resume recovery
are implemented: account-scoped identifiers, explicit read-only resume, no duplicate submission. R10 dedicated
fixtures, guarded full-store checks and a disposable PostgreSQL CI job are implemented. The owner-run isolated
PostgreSQL check passed **5/5**, exit 0 in 64s (2026-11-12; `dev/db_audit/postgres/2026-11-12_api_integration_report.txt`).
The owner-run application audit now reaches section 28 with no SQL errors; traffic/finance results, grants and
comment coverage match expectations. The statistics follow-up confirms stored statistics on all 15 project
tables (119 columns), with row estimates matching the exact audit counts; missing activity timestamps do not
require a rebuild on this evidence. The owner schema export has been reviewed and promoted through migration
028: three M17 views and 56 matching comments added, no existing definitions changed; prior snapshot preserved.
Owner finance/reference validation passed all 8 validation stages, exit 0 in 11s: all 52 weeks match the
independent calculation and RBAC leakage is 0 (`dev/db_audit/postgres/2026-11-12_finance_views_report.txt`).
The owner rebuilt the web service: runtime inspection now confirms `project-web-1` uses `portpilot-web:local`
and /login returns `Sign in — PortPilot`. Sign-in is currently blocked because the host API is stopped:
both the host health probe and the container probe return connection-refused on port 8000. The container's
API URL is the configured `http://host.docker.internal:8000`.
**Immediate next owner step:** start `uv run python pipelines/scripts/api/Serve.py` in a separate terminal,
keep it running, then verify API health and sign-in. End-to-end live login is not yet verified.
Owner-requested Finance cleanup (2026-11-12): the duplicate Smart View tab has been removed from source;
custom chart creation stays on Charts (`/views`). Rebuild the web service to deploy this latest UI change.
Then `Traffic_link_check.py`. Full-data API integration, real-model traffic acceptance, Power BI parity,
pushed CI and the Git checkpoint remain open. Full handoff is in the plan; earlier dated summaries are historical.

**DONE 2026-11-11: PortPilot repository rebrand** — owner-requested product name, SVG P/navigation logo, browser
icon, web/API/report branding, compatible configuration/upload formats and renamed Power BI project. ADR-068;
implementation record `dev/history/archive/2026-11-11_PortPilot_rebrand_plan.md`; ongoing compatibility inventory
`docs/brand/README.md`. Browser production suite 100 passed / 50 intentional skips; frontend static all passed;
Python lint/type findings 0; upload/Power BI/skill compatibility 4/4. Existing external identifiers and historical
evidence are retained. **Owner operational follow-up:** scheduler migration and Power BI live parity, then commit.

**DONE 2026-11-07: the manager's request in words; the pack and the dashboard change together** — plan archived as
`dev/history/archive/2026-11-07_Approver_request_plan.md` (owner R1–R5, ADR-067). The manager writes one request; one
structured call proposes the pack's own decision kinds or asks back; code checks (shapes, caps, the week rule, note
numbers, an explicit approve / reject word); he confirms; a revise runs first. `Weekly_pack.py resume --request`,
`POST /packs/{thread}/request` + `/confirm`, `GET /finance/pack`; migration **024**; Power BI page **Approved Pack**.
Evaluation: exact **0.9667** (EN 1.0, AR 0.9333), invented numbers 0; live on W15 (published 2026-11-07, Power BI =
API = deck). **Open (owner):** one commit of this plan (R5). Monday 2026-11-09's task
builds **W16**.
**Also closed 2026-11-07:** the approver-additions plan, archived as
`dev/history/archive/2026-11-07_Pack_approver_additions_plan.md` (live check on W14; its commit C4 the owner's).
**Closed 2026-11-09: the external-context plan**, archived as `dev/history/archive/2026-11-09_Pack_external_context_plan.md`
(a code node fetches the week's Suez transits + news; ec2 kept; live W16 slide 9 from code; D-EC-5 / D-EC-6 fixes;
ADR-050 am. 4, ADR-051 am. 7). **Open (owner):** reject W16:3, review W16:4; the commit. (Done 2026-11-14: both rejected, W16:5 approved and published.)
**Closed 2026-11-14 (see the top of this section):** the traffic-billing link plan, now
`dev/history/archive/2026-11-14_Traffic_billing_link_plan.md`. The state of 2026-11-09, kept as written: Phases 1–3 are done: migrations 025
(PortWatch), 026 (the labelled scenario, α = 1.6) and 027 (M17 `kpi_traffic_link`) are applied, plus 028 (comments on
024's view columns, D-TL-5). Live = no link in any week; scenario = link at 52 weeks. **Next:** Phases 4–6 (the pack's
`context.link`, Validator V10, acceptance). **Open (owner):** the snapshot refresh + the full audit.
`docs/plans/JIT_arrival_plan.md` (PROPOSED 2026-11-08: Just-in-Time arrival advice, a third Operations product;
decisions J1–J7 open).
`docs/plans/Model_flexibility_plan.md` (APPROVED 2026-11-13: the model per role in one tracked file, any provider
as an entry, limits / temperature / timeout per model, a capability probe and a swap procedure; owner decisions
M1–M7 taken; starts after traffic Phase 6 because it edits `llm.py` / `roles.py`).
**In parallel: the frontend plan** —
`dev/history/archive/2026-11-16_Frontend_plan.md` (APPROVED in its own session 2026-11-06). D-FE-11 (2026-11-14, owner request): the
Ask composer's "+" attaches documents from a conversation's first message (web-only, the API's upload checks
unchanged) and the "Today" tab is removed (the wordmark opens `/`); mock-API browser suite 130 passed; the real-API
the web container is rebuilt with it; the real-API smoke `web/scripts/attach-smoke.mjs` 12 / 12 (the answer comes
from the attached document, EN + AR). That smoke found a server defect, fixed: the upload reader's child wrote its
JSON in the console code page, so every upload failed with `E_PARSE` when the API ran without `PYTHONIOENCODING`
(`pipelines/lib/upload_reader.py` now writes UTF-8 bytes; guard in `Upload_validation.py` Phase 4).

**Agents Stage 2 walk-through — DONE 2026-11-05:** `dev/history/CHECKPOINT_agents_stage2.md` (Phases 9–12 in plain Egyptian
Arabic, like the Stage 1 one; the 2026-11-01 close had not included it — an omission the owner pointed out).

**FastAPI — CLOSED 2026-11-05** (`dev/history/archive/2026-11-05_FastAPI_plan.md`, implementation record at the top; ADR-064
+ ADR-065 Accepted). The API over every product (`pipelines/api/`, 127.0.0.1, one process): login, conversations with
memory, questions / pack decisions / route advice as runs with SSE events, uploads, the watch, problem+json errors,
security headers, `audit_log`, Sentry + LangSmith + an access log; the LLM quota and caches shared across processes.
`Api_check.py` 10 / 10, `Load_test.py` 5 / 5, `Api_smoke.py` 5 / 5 (real models), `Memory_check.py` 4 / 4 (two real
runs, resolution EN / AR 1.0), injection set v3. **Open for the owner:** decide the 2026-11-09 pack through
`POST /api/v1/packs/{thread}/decision` (a login from `Api_admin.py`); **commit** the whole plan (A4: one commit).

**History of the FastAPI phase:** the plan was written as `dev/history/archive/2026-11-05_FastAPI_plan.md` (`Status: PROPOSED`) in a new
session, starting from the concurrency requirements below ("API phase → concurrency requirements"), and waits for the
owner's approval before any code (owner, 2026-11-03). **Written 2026-11-03 (PROPOSED):** owner decisions A1 local
login, A2 PostgreSQL only (Redis / Dramatiq / OTel deferred with a measured trigger), A3 "intelligent memory" →
conversation memory designed in the plan's §6a (ADR-065 to come), A4 one commit at the end. **APPROVED 2026-11-03**
(owner). **P0 DONE 2026-11-03:** packages (fastapi 0.150.0 with its own SSE, uvicorn, python-multipart, filelock;
two transitive packages held by the two-week rule), `pipelines/api/` skeleton + `Serve.py` (127.0.0.1, one process),
`Api_check.py` Phase 0 ✅, lint ratchet 0, ADR-064 PROPOSED. **P1 2026-11-03:** migration 023 APPLIED (schema `api`,
`api_writer`, the shared LLM counters in `agent_state`; audit §25 as expected, 0 errors), `Api_admin.py`,
`passwords.py`; login `ports_api` created by the owner 2026-11-04, `check_api_user.py` 21 / 21 PASS → **P1 DONE**.
**P2 DONE 2026-11-04:** the LLM quota, per-minute budget and caches shared across processes (PostgreSQL counters +
file locks; `Load_test.py` 5 / 5; no-regression run green after one cache fix, D-F2-3). A local browser-debugging tool added
(ADR-060 amendment 2, locked-down config). **P3 DONE 2026-11-04:** sign-in / sign-out / `/me` / `/health/ready`, the
problem+json error mapping, request ids, security headers, CORS, body limits, `audit_log` (`Api_check.py` Phases 0–3 +
9 ✅). **P4 DONE 2026-11-04:** conversations, questions as runs (202 + SSE events of the contract), the run
executor with 429 / 409 / 504 back-pressure, per-thread locks, stored answers; `Api_check.py` Phases 0–5 + 9 ✅ (50
at once → 24 accepted, 26 × 429, 0 × 500). **P5 DONE 2026-11-04:** uploads in a conversation (memory only,
the ADR-042 validator + screening + local bge-m3), reaching the supervisor's document tool as a separate
`untrusted_upload` list through the run context; manager promotion requests; injection set v3 (+ an upload-planted
instruction) — two real runs, every gate held. **P6 DONE 2026-11-04:** the weekly pack (list / show / preview /
decision as a run / deck), route advice as a run, the voyage-watch alerts and runs; `Api_check.py` 10 / 10 ✅. Next:
P7 (observability, THREAT_MODEL web table, the real smoke, ADRs) and P6m (conversation memory). **P7 DONE
2026-11-04:** Sentry as the fifth entry (per-event tags), the access log, the query-embedding count, the OpenAPI
snapshot in the CI, the THREAT_MODEL web table, ADR notes; the real smoke `Api_smoke.py` 5 / 5 (EN + AR questions,
an upload question, a route advice on the real models). **Open for the owner:** decide the next real pack (Monday
2026-11-09) through the API. **Next: P6m — conversation memory** (its frozen golden set first, for the owner's review).

**Engineering hygiene follow-ups — CLOSED 2026-11-03** (`dev/history/archive/2026-11-03_Hygiene_followups_plan.md`, ADR-063
amendment 2): the lint baseline paid down to **0** (ruff 48 → 0, pyright 276 → 0; every check re-run with 0 files
changed); THREAT_MODEL LLM01 measured by `Injection_eval.py` on a frozen 11-item injection set, two real runs: prompt
leak 0, planted instruction followed 0, finance leak 0, escalations refused (`injection_eval_2026-11-03.json`);
`D:\Project_wip` deleted. D-H3 closed the same day (owner: widen): the screening now flags all 6 planted shapes (ADR-042 note; corpus false
positives still 0), set v2 re-run on the real model, every gate held. D-H2 closed the same day: every writer of a tracked .json / .jsonl / .csv now writes LF (`newline="\n"`,
`lineterminator="\n"`; 36 sites in 23 files), each re-run = its committed bytes; D-H4 (a re-run overwrote `bakeoff_results.json`'s run statistics) restored by
the owner before the commit. Committed and pushed as `92003ee`; **CI run #2 green** (2026-11-03, 39 s; its Node 20
deprecation warning fixed the same day: `actions/checkout@v5`, `astral-sh/setup-uv@v7`).

**Weekly pack improvement — CLOSED 2026-11-03** (`dev/history/analysis/financial_intelligence/implementation_roadmap.md`,
implementation record at the top; the folder stays in place). Phases A–F: migrations 021 / 022 (`finance_kpi` +16
weekly columns, customer watchlist, twins), `audit.ytd`, the redrawn slides + layout fixes (D-C5-3, one-line titles),
Validator **V9** rules 1–8, the two skills reviewed by the owner 2026-11-02, **c5b kept** on a hand-check (ADR-051
amendment 4, ADR-052 fifth use; Stage 1 packs baseline `stage1_eval_2026-11-02_c5b.json`), Power BI (ADR-048
amendment 1); W13 published 2026-11-03 on the new code. No-regression re-run 2026-11-03 (D-RR-1, ADR-052 sixth use):
finance Q&A vs dp127b "tie: keep"; Stage 2 vs c1 stopped after repeat 1 on the Arabic gate by one Writer slot-form
error on a non-finance item, every `finance_kpi` number right → closed on the owner's hand-check; baselines unchanged.
~~Open for the owner: delete `D:\Project_wip` (the old parallel copy).~~ Done (found deleted 2026-11-03).

**Observability — CLOSED 2026-11-02** (`dev/history/archive/2026-11-02_Observability_Sentry_plan.md`, ADR-062 + amendment 1):
S1 Sentry errors / logs / the weekly pack's cron monitor — the first real check-in arrived ok on 2026-11-02 08:30Z;
S2 LangSmith mirror, S3 review queue, S4 new-issue alert. **D-S1-6 closed 2026-11-03** (owner: "اربطه"): the monitor's detector
10829356 (`nilegate-weekly-pack`) connected to alert 6273246 through the Sentry API — a missed / failed Monday now emails.
**Dependency upgrade — DONE 2026-11-02** (`dev/history/archive/2026-11-02_Dependency_upgrade_plan.md`, ADR-063 note): 8
packages to their lowest fixing releases (+ `langgraph-checkpoint` 4.3.0), `pip-audit` 63 → 0, every check green.

**Agents plan — CLOSED 2026-11-01** (`dev/history/archive/2026-11-01_Agents_plan.md`, implementation record at the top).
Its last stage, for the record: **Stage 2 — Phase 12 (the supervisor over both products) DONE (2026-10-30)** — plan §6d (P12-1…P12-5 as recommended; S1–S5 + candidate c1 each approved before their code), ADR-059:
one `create_agent` over the Stage 1 + Stage 2 tools + the product tools `route_advice` (the ADR-057 graph as a
tool), `voyage_eta`, `watch_alerts`, `fleet_customers`; a code router (≤ 5 tools per question, EN + Egyptian
Arabic) drops the tools the asker may not use → partial answers name the refused part; every number a slot; a model
view at the boundary + a customer join guard in code (c1); CLI `Ask.py ask | show | list | prune` (replaced
`Finance_qa.py`), one thread + one LangSmith trace per question. **Evaluation (`Stage2_eval.py`, the 57-item golden
set frozen first, the done-when fixed before any run):** the baseline `stage2_eval_2026-10-29.json` passed every hard
gate but completeness EN 0.7622 < 0.85; **candidate c1 `stage2_eval_2026-10-30_c1.json` = the Stage 2 baseline —
done-when MET**: completeness EN 0.9816, AR 0.95, leakage 0, twins / abstention / numbers / traceability 1.0 in both
runs, ADR-052 "keep (better)"; the Groq fallback cannot take the 17–20K-token requests → flash-lite alone for those
(ADR-045 amendment 3). Not fully right: o01 (the voyage status word), c07 run 2 (the saving). **D-P12-7 DONE
2026-10-31:** the scheduled run was rejected (a01: a 2024 question answered with a 2025 figure) → a code year guard
(D-P12-12) → `stage1_eval_2026-10-31_dp127b.json` = ADR-052 keep (better), every gate, completeness EN / AR 1.0.
**Stage 1 candidate c4 — DONE** (owner 2026-10-30: close `planted_all` before the commit; coded and checked on fake models:
a pack whose Writer fails its rewrites gets code's texts in place of the failing ones and reaches the approver marked
degraded, so slide 8's audit table is never lost; a code budget-miss table on slide 5, rule M9a; ADR-051 amendment 3)
compared live 3 + 3 packs-only runs on 2026-11-01 — **KEPT** (owner, on a hand-check): planted 6 / 6 in every
run (before 2 · 3 · 0 / 6), published 32 / 33 (before 24 / 33), recall 0.9655 vs 0.7471; the scored reject was one
true sentence (scorer rule widened, D-C4-1; ADR-053 result note) → **D7 `planted_all` met** → the plan's
implementation record + archive DONE 2026-11-01 → **the one commit by the owner (Stage 2 + c4 + Sentry S1)**.
Later candidates (not gates): o01's status word, c07's saving; FastAPI (PLANNED).
**Weekly pack improvement — study DONE and validated 2026-10-31 (data-validation review), plan
APPROVED (W-R1…W-R8 as recommended); Phase A DONE 2026-10-31 (migration 021 applied: `Finance_views_check.py` 8 / 8,
`Tools_check.py` 10 / 10, snapshot + audit refreshed); Phases B–E after c4:** the owner's goal is a better
**weekly** pack (the agent's 10 slides), not a yearly deck. Study rewritten in `dev/history/analysis/financial_intelligence/`
(W12 viewed slide by slide; week-by-week analysis W1–W9: typical weekly swing, 13-week position, drivers' invoice
counts, customer receivables watchlist — the #1 customer's AR ≈ 95 % of its 13-week billing at W12 — overdue flows and
concentration, DSO split, Writer over-claims; gaps C1–C10 / L1–L8). Plan `implementation_roadmap.md`: owner decisions
W-R1…W-R6, then migration 021 (new `kpi_weekly` / `kpi_customer_13w` / `kpi_weekly_category` columns, M12–M15),
`finance_kpi` columns, deck changes on slides 2–10 (still 10 slides), Validator V9 (claim check) + skill edits,
candidate **c5** vs c4 under ADR-052. Before c4 only the SQL layer (the tools read explicit columns, so new view columns change no c4 run).
**Side product (ADR-061, kept by the owner):** an annual executive deck built earlier on a misread scope
(`pipelines/scripts/finance/Executive_*.py`, `reports/executive/2025/`), M12 in `finance_metrics.md`, Power BI
Executive page; Power BI fixes kept (Exceptions status card + all-year findings table, Overview note). These files
go into the one Stage 2 commit.
**Observability plan — Sentry S1 DONE on the checks 2026-10-31 (started before the Stage 2 commit by the owner's
choice; `dev/history/archive/2026-11-02_Observability_Sentry_plan.md`, ADR-062):** `pipelines/agents/monitoring.py` in the four
CLIs' `main()` — errors + WARNING+ logs, the one free cron monitor on the weekly pack (`nilegate-weekly-pack`), no
LLM spans; `Monitoring_check.py` 5 / 6 ✅. **Open:** the owner's `SENTRY_DSN` in `.env` → the live Phase 6 → the
first real check-in (Monday 2026-11-02 10:30). Then S2–S4 after c4. Original scope (owner 2026-10-30):
`sentry-sdk` error capture in the scheduled jobs and CLIs + Sentry Crons check-ins for the
scheduled tasks + Sentry read access (OAuth, connected 2026-10-30, org `terbo`, project `python`); LangSmith stays the LLM
tracer (ADR-054), Sentry gets no LLM spans, a `thread_id` tag links the two; issues are read freely and changed
(resolve / assign / comment) only with the owner's yes per change; free Developer plan (limits to be confirmed).
The same plan adds **LangSmith Datasets & Experiments as a mirror (PLANNED, owner 2026-10-30)**: the frozen golden
sets and the code scorer stay local and authoritative (sha256 in git, ADR-052); after each evaluation a copy of the
golden set (its sha256 in the dataset's description) and the per-item results are logged as an experiment from the
reply cache (0 new model calls, traces only), for item-by-item candidate comparison in the UI. **Plus a LangSmith
automation rule (PLANNED, owner 2026-10-30):** a trace with an error or a `refused:` tag goes to an annotation queue
(no LLM judge, 0 model calls; free-plan automation limits to be confirmed), so real failures are reviewed by the owner
and the useful ones become new golden-set items in the next frozen version. No LangSmith evaluators for the gates:
the code scorer stays the acceptance rule (ADR-052); an LLM judge, if ever, only as a reported metric (its own ADR).
**Engineering hygiene — DONE 2026-11-01** (ADR-063, `dev/history/archive/2026-11-01_Engineering_hygiene_plan.md`): ruff +
pyright through a lint ratchet (`dev/tools/lint_ratchet.py`, baseline 325), CI on GitHub Actions (first run at the
owner's push), Dependabot, `pip-audit` (**open: 63 advisories in 8 packages — one upgrade with the full checks after
the 2026-11-02 firing**), `docs/THREAT_MODEL.md`, Mermaid diagrams in ARCHITECTURE §1.1. Original scope
(owner 2026-10-30; free tools only, no paid plan) — from a production-readiness
review of the project (most items already exist: ADRs, RBAC, approval interrupt, checkpoints + resume, fallback,
slots, golden-set regression, LangSmith). (1) **Ruff + type checking + CI:** `ruff` and a type checker (`pyright` or
`mypy`, chosen in the plan; started on `pipelines/agents/` and `pipelines/lib/`) as uv dev dependencies, then GitHub
Actions (free minutes) running `ruff` and the checks that need no database (fake models, pure functions); the full
`*_check.py` runs stay on the owner's machine (they need the loaded PostgreSQL / MongoDB / Qdrant). (2) **Security:**
Dependabot alerts + `pip-audit` (via `uvx`); `docs/THREAT_MODEL.md` mapping each OWASP Top 10 for LLM / Agentic
applications item to the project's control (or a gap), extended with the web items (XSS, CSRF, SSRF, CORS) when the
API and the frontend exist (ADR-060); prompt-injection items (instructions inside
`search_documents` results / uploads) in the next frozen golden-set version. (3) **Mermaid diagrams** in
`ARCHITECTURE.md`: the overview and the four graphs (`weekly_pack`, `route_advice`, `voyage_watch`, the supervisor).
Not planned, by design: cloud deployment (needs a card), Kubernetes / Terraform / Kafka (one machine, one process),
Langfuse (duplicates LangSmith, ADR-054), microservices (ADR-036), an outside plan / TDD / worktree workflow (owner
2026-10-31: the project keeps one active plan in `docs/plans/` and `*_check.py` instead of pytest).

**RAG retrieval CLOSED 2026-10-08** — plan archived as `dev/history/archive/2026-10-08_RAG_Embeddings_Qdrant_plan.md` (implementation record at the top). Result: Gemini `gemini-embedding-2` vectors (ADR-037) for the 2,163 chunks in Qdrant `nilegate_docs`; `search_documents` (`pipelines/lib/retrieval.py`) with RBAC inside Qdrant, exact dense + Jina rerank (ADR-038; balanced 0.850, RBAC leakage 0; baseline `Data/processed/rag/eval/results_2026-10-08.json`); three-level evaluation (ADR-040); conversation uploads with a local bge-m3 lane (ADR-042 – ADR-044); `documents.ingested_at` filled (migration 011). Phase 9 clean-up: the bake-off vectors moved to `Data/embeddings/bakeoff/`, the two rejected local models removed (`Upload_eval.py` keeps their recorded rows), promoted documents' migrations carry `ingested_at`.

**Agents plan Stage 2 — Phase 11 (`voyage_watch`, C Voyage & Disruption Watch) CLOSED (2026-10-28, autonomous
session under the owner's grant — P11-1…P11-10, D-P11-1, D-P11-2 and the skill `voyage-watch-brief` reviewed and approved by the owner
2026-10-29)** —
plan §6c, ADR-058: the fleet at the clock, rule-based ETA R (fixed before measuring), next-leg weather
(Open-Meteo) and Suez traffic (PortWatch) → fixed alert rules in code, saved before any model call; one `writer`
brief with number slots ⇄ a code Validator; one thread + one JSON file per run (`reports/voyage_watch/`), CLI
`Voyage_watch.py run | scheduled | alerts | show | list | prune`, every 12 h on a replay clock (task "PortPilot Voyage Watch"
registered 2026-10-29 by `ops/scheduler/register_voyage_watch.ps1`, 10:30 + 22:30 local; the first firing lost
848 / 1,448 weather points to Open-Meteo's per-minute limit, which counts each location → D-P11-2: batches
paced ≤ 400 locations / min, one retry after 65 s, failed points recorded with their reason). `Voyage_watch_check.py` Phases 1–7 + 4s ✅: **ETA MAE 0.885 h vs the naive baseline 117.8 h** (126 replayed
cuts; S2-D5 met; no ML needed; R reproduces the generator — the synthetic speed is constant), planted events
precision = recall = 1.0 (weather 27 / 27, Suez 40 / 40), 49 / 49 planted brief errors caught, the real model's brief
passed. Nothing committed. **Next (then): Phase 12 — the supervisor over both products** (done 2026-10-30, above).

**Agents plan Stage 2 — Phase 10 (`route_advice`, B Route & Cost Advisor) CLOSED (2026-10-27)** — plan §6b
(P10-1…P10-4, D-P10-1 / D-P10-2), ADR-057: code computes every number (the two routes, sea days, fuel and its SDR
cost, the Suez dues, the Cape − Suez difference, the Suez traffic trend), one `writer` call writes the advice with
number slots, a code Validator keeps the owner's rule (the cheaper route unless a cited risk; days not priced), one
PostgresSaver thread per question (30-day retention), CLI `Route_advice.py ask | show | list`, skill
`route-cost-advice` (reviewed). `Route_advice_check.py` all phases ✅: 20 rows = an independent computation, 64 / 64
planted errors caught, the real model 8 / 8. Stage 1 checks unchanged. Nothing committed.

**Agents plan Stage 2 — Phase 9 (Stage 2 tools) CLOSED (2026-10-27)** — plan §6a (P9-1…P9-8, deviations
D-P9-1…D-P9-11), ADR-055 / ADR-056: `sea_route` (searoute restrictions: Suez vs the Cape), `vessel_params` (migration
020: `vessel_performance` from the Fourth IMO GHG Study 2020 + the owner's dated VLSFO price in SDR), `voyage_status`
(our synthetic voyages up to the run's clock `as_of`, MongoDB read-only user `nilegate_reader`), `marine_weather`
(Open-Meteo); no live AIS. `dev/checks/agents/Stage2_tools_check.py` Phases 0–5 ✅ (500 voyages = the
generator, distance left ≤ 1.79 nm, RBAC 100 × 4, leakage 0); `Tools_check.py` 8 / 8 unchanged. Nothing committed
(the owner commits once when Stage 2 closes).

**Agents plan Stage 1 CHECKPOINT DONE (2026-10-27)** — PR mahmoudsameh00/nilegate-ports-ai#1 merged into `master`
(merge `5e49ad6`); follow-ups of the first missed-Monday firing fixed (D-P8-17 preview per content, D-P8-18 trigger in
local time, D-P8-19 unit after a hyphen); W12 published; D-P8-20 decided 2026-10-29 (ADR-052 amendment 2: a fixed deck set
for non-Writer changes, three runs per side for Writer changes, margin 0.03; the fixed-deck mode not yet coded).

**Agents plan §5f — Phases 7–8 closure DONE (2026-10-23; F1–F9)** — no open point left before the Stage 1
checkpoint (K1–K9, owner decisions C-1…C-4, order F1…F9). Done: K1 the owner's review (18 points: 13 accepted, 5
changed); F1 `show` prints the comment, `form_fixes` in `run.json` / `report`, `list_runs` kept with a pinned reason;
F2 the finance Q&A agent on LangChain `create_agent` + `Finance_qa_check.py` 6 / 6 + CLI `Finance_qa.py` (replaced by `Ask.py` 2026-10-29, Phase 12 S4); F3 a real
planted budget miss (migration 018, findings v3, planted gate `planted_all` = 6); F4 Q&A golden set v2 (42 items);
F5 the tariff Notes rule (migration 019, `review` = error | manual_review); F6 the Power BI Exceptions page; F7 the
new fallback `nvidia/nemotron-3.5-super-vl:free` (1 / 2 forced-fallback packs published, dots 0 / 2; ADR-045
amendment 2); **F8 the confirmation evaluation = the final Stage 1 baseline** `stage1_eval_2026-10-23_confirm.json`:
**D7 not met** on one gate, planted findings 2 / 6 · 3 / 6 (packs 7 / 11 · 10 / 11: a pack the Validator stops has no
deck, so its planted findings count as missed; no wrong deck published); deck numbers, claims, traceability 100 %,
RBAC leakage 0, abstention 1.0, Q&A EN 0.96 / AR 0.95, narrative recall 0.79; the scored false alarms were a scorer
false positive (real 0, fixed by rule, D-P8-16, ADR-053); F9 docs + every check green (Tools 10 / 10, Weekly_pack
7 / 7, Deck 4 / 4, Finance_qa 6 / 6, Scheduler 6 / 6, Stage1_eval 1–4, frozen inputs 0 changed). **Next:** the owner's
one commit → the Stage 1 checkpoint PR of `feat/agents` → Phase 9 (Stage 2 tools; decisions answered 2026-10-23:
plan §6a / §7 — no live AIS in Stage 2, the rest the recommended options). Follow-up (not a gate): the Writer's
publish rate on the free model.

**Agents plan Phase 8 CLOSED (2026-10-22)** — ADR-054, plan §5e (P8-1…P8-4, deviations D-P8-1…D-P8-12): Windows
Task Scheduler task "PortPilot Weekly Finance Pack" (Monday 10:30, logged-on only; `ops/scheduler/register_weekly_pack.ps1`,
registered on the owner's machine) runs `Weekly_pack.py scheduled` — the next week of the 2025 replay as `PACK_RUN_AS`
(Finance manager 6), one pending pack at a time, a pack stopped mid-run resumed, a stopped attempt retried once, the
firing waits for PostgreSQL, a lock, a toast; retention = archive (`reports/_log/threads_archive.jsonl`) then
`delete_thread` for ended threads older than 30 days, pending never; `prune`, `report` (G5 edit rate). LangSmith
(free developer plan, project `nilegate-agents`): a tracing context per graph run of `run` / `resume` / `scheduled`
(+ `Stage1_eval.py` with `EVAL_TRACE=1`), never the global switch. `Scheduler_check.py` **6 / 6 ✅** (incl. a trace
read back from LangSmith); Weekly_pack_check 7 / 7, Deck_check 4 / 4, Stage1_eval Phases 1–4 ✅ (0 calls).
**Done-when met (2026-10-22):** two firings stopped on a Gemini 503 ("high demand") in the Insight node; the third
resumed `weekly_pack:live:2025-W11:1` from its checkpoint and reached the approval (toast, trace
`launched_by:task_scheduler`); W11 then edited (one sentence) and approved by Finance manager 7 → published; G5
edit rate 0.5 over W10 + W11. Monday 2026-10-26 the task makes W12. **Found:** the ADR-045 fallback (OpenRouter
`nemotron-3-super:free`) answers 404 on every request (NVIDIA "Function not found for account") → no working
fallback for the pack's Insight / Writer that day (closed 2026-10-23 by ADR-045 amendment 2, §5f F7). **Next: the Stage 1
checkpoint** (§5 row "S1 ✔": the owner's commit + a PR of `feat/agents`), then the Stage 2 decisions (§7, S2-D1…)
before Phase 9.

**Agents plan Phase 7 CLOSED (2026-10-20)** — ADR-053 (+ ADR-052, the acceptance rule), plan §5d (P7-1…P7-4,
deviations D-P7-1…D-P7-12): 11 golden weeks chosen by rule and frozen (4 test + 7 live) with their evidence and 38
hand-written findings; migration 017 (`finance_test` twin KPI views, applied, `verify_readonly.sql`
§21); the finance Q&A agent (`pipelines/agents/graphs/finance_qa.py`, skill `finance-qa`, English + Egyptian Arabic);
a 40-question golden set; `Stage1_eval.py` (scorers proven on hand-made failures, D7 + §8a gates, two runs per setup).
Results: baseline D7 not met; candidate c1 (Validator false-alarm fixes + Q&A prompt lines) kept by ADR-052 = the
baseline (`stage1_eval_2026-10-20_c1.json`): deck numbers 100 %, **planted 5 / 5**, false alarms 0, claims 100 %,
RBAC leakage 0, Q&A EN 0.96 / AR 1.0, narrative recall 0.69; **misses** abstention 0.86, traceability 0.996 in one
run, publish rate 10 / 11 and 6 / 11 → owner: close Phase 7, keep c2 for later. **Update 2026-10-22:** c2 rejected; c3 (Validator false-alarm fixes, code-fixed slot form) accepted by an owner exception to ADR-052 = the baseline `stage1_eval_2026-10-22_c3.json`: packs 10 / 11 in both runs, recall 0.88, abstention 1.0, Q&A EN 0.96 / AR 0.95; D7 not met by one slot; tuning stopped. Findings: the planted budget miss is
not a miss (D-P7-1); flash-lite's free tier = 500 requests / day (one full evaluation per day). **Next: Phase 8** —
scheduling, LangSmith, checkpoint retention.

**Agents plan Phase 6 CLOSED (2026-10-19)** — ADR-051, plan §5c (owner decisions P6-1…P6-8): the weekly deck
(`pipelines/agents/deck/`). The Writer writes numbers as **slots** (`{evidence[row]:field|format}`; code writes the
rounding, sign, unit, `|dir` for up / down); code draws slide 1, the KPI tiles, every table and native chart, the
footnotes and the sources slide (template as code: 16:9, PortPilot navy / teal); the **Validator v2** binds every
number to one (evidence, row, field) — V1–V7: citations, numbers, label, shape, evidence per slide, direction,
attribution (drivers = top three, known invoices, the named row, no total on one row, no unit / direction written
twice) — and **V8 reads the rendered PPTX back** (every shape a contract name; the template allowlist = the
template). A rewrite is a `DeckPatch` of the failing texts (≈ 20 % of a first draft's prompt); the approver opens a
preview (`reports/_drafts/`); the publisher saves `deck.pptx` after its read-back. Skills `deck-style-guide` and
`number-validation` rewritten (owner-reviewed). `Deck_check.py` **4 / 4 ✅**: 52 / 52 clean decks pass V1–V8 (0 false
alarms), **100 / 100 planted wrong numbers caught** (17 draft + 8 file classes × weeks 5 / 10 / 23 / 49 — the done-when),
every real failure replayed. `Weekly_pack_check.py` **7 / 7 ✅**; real models (5 runs, reported per P6-8): the last
published 3 / 4 (the fourth stopped on a real Writer error the Validator caught), Writer calls ≤ 12.4K tokens (17.0K
before). **Next: Phase 7** — evaluation (§8) on golden weeks + finance Q&A golden questions, with the §8a generation
checks (G1–G6, still PROPOSED: the owner reviews them first) and the planted budget miss of `finance_test`.

**Agents plan Phase 5 CLOSED (2026-10-19)** — ADR-050, plan §5b (owner decisions P5-1…P5-8 + three S6 decisions):
the LangGraph `weekly_pack` workflow (`pipelines/agents/graphs/`): Data Readiness gate, KPI and Invoice Auditor as
code over the Stage 1 tool functions, the Insight agent (LLM ⇄ `ToolNode(STAGE1_TOOLS)`), the Writer (`DeckDraft`),
a code Validator (numbers = cited structured evidence after the allowed roundings; ≤ 2 rewrites), the approval
`interrupt()` (Finance manager / CEO; approve, edit → re-validated, reject; logged) and the Publisher
(`reports/2025-W<ww>/`, save only). Checkpoints: migration 016 (schema `agent_state`, `agent_writer` DML only),
login `ports_agent`, `PostgresSaver.setup()` as a deployment step; `durability="sync"`. Roles over `llm.py`
(`roles.py`): the real prompts (9.7K–17K tokens) exceed Groq's 8K TPM → **ADR-045 amendment 1** (the pack's Insight /
Writer on Gemini flash-lite + OpenRouter nemotron). `Weekly_pack_check.py` **7 / 7 ✅**: 52 / 52 weeks to the
approval and published with fake models, the approval rules, the Validator loop + 26 rule cases, a process killed
inside the Writer resumed from PostgreSQL in another process, real models on weeks 5 / 10 / 23 / 49 (2 published, 2
`validation_failed` on real Writer errors), the schema / dataset contract. CLI `Weekly_pack.py`; first real pack:
week 10 approved by the CEO. **Next: Phase 6** — PPTX template (PortPilot style) + Writer + Validator (signs and
citations of the Writer, numbers bound to their fields — G1, the full template allowlist; done when the Validator
catches every planted wrong number in a test deck).

**Agents plan Phase 4 CLOSED (2026-10-19)** — ADR-049, plan §5a (owner decisions P4-1…P4-8): six Stage 1 tools in `pipelines/agents/tools/` under one result contract (`finance_kpi`, `invoice_audit`, `compute_toll`, `search_documents`, `suez_transits` via IMF PortWatch, `web_search` via Tavily), the user and the dataset from the run context (never a model argument), RBAC in every tool; migration 015 (`finance.invoice_audit` + twin in `finance_test`); external calls cached / 10 s timeout / "context unavailable"; the skill loader + 6 Stage 1 skills. `Tools_check.py` **8 / 8 ✅ (2026-10-19)** (compute_toll = 1,000 invoices, finance_kpi = the views on 52 × 5 and the hand weeks, invoice_audit = the answer key 5 / 5 with causes and false alarms 0, RBAC matrix 100 × 7 leakage 0, external failure modes, live PortWatch and Tavily, skills within budget). Finding: 3 real duplicate charges in the original invoices (336,909.00 SDR, both copies paid). Migration 015 applied by the owner (2026-10-19): snapshot refreshed, `verify_readonly.sql` §18 (14 views) / §19 as expected, 0 errors (`dev/db_audit/postgres/2026-10-19_after_015_report.txt`, `ANALYZE` re-run: statistics had been reset); Tavily key set. All 6 skills reviewed by the owner (2026-10-19, 13 fixes, each turned into a check) and retrieved / web text now screened for injection (`tools/trust.py`); final run `Tools_check.py` 8 / 8, pending none. Open items for later phases in the plan's Progress (budget-miss view for Phase 7, Exceptions page in Power BI, Validator allowlist / numbers from structured fields only, tariff Notes rules, token budget). Phase 5 followed (closed 2026-10-19, above).

**Agents plan Phase 3 CLOSED (2026-10-15)** — ADR-048: Power BI Desktop 2.158 project `powerbi/PortPilot_Finance.pbip` (TMDL + PBIR in git), DirectQuery on 12 `finance` views (+ migration 014 `kpi_weekly_trend`) through the read-only login `ports_bi` (`finance_bi` only, 11 / 11); model by Power BI Desktop's TMDL editing: `Week` filters every table (18 relationships, referential integrity off), 38 thin measures (SELECTEDVALUE / HASONEVALUE-guarded / SUM; no KPI logic in DAX), 1 label column; 5 pages — Overview, Revenue, Receivables, Customers, Exceptions (placeholder until the Auditor tool) — with one synced single-select week slicer. Done-when met: every number of pages 1–4 = `finance.kpi_weekly` read from PostgreSQL for weeks 5 / 23 / 49, breakdowns sum to the week's KPI. Docker containers now `--restart unless-stopped`. **Next: Phase 4** — Stage 1 tools (§3) + tests (external tools behind cache + timeout), the skill loader and the Stage 1 skills (`pipelines/agents/skills/`), including the Auditor tool that fills the Exceptions page. Still open: the owner's review of §8a (G1–G6, PROPOSED).

**Agents plan Phase 2 CLOSED (2026-10-14)** — ADR-047: schema `finance` = 12 plain views (dims, `fact_invoice` with the derived due date, `fact_payment`, `fact_ar_snapshot` as-of status, KPI views `kpi_weekly` / `kpi_weekly_category` / `kpi_customer_13w` / `kpi_overdue_list`), migration 013; definitions in `docs/finance_metrics.md` (DSO = AR ÷ billed last 91 days × 91, warm-up weeks 1–13 on the available window, strict ISO weeks as of Sunday); `Finance_views_check.py` 7 / 7 ✅ (views = independent pandas reference on all 52 weeks; hand-check weeks 5 / 16 / 23 / 49 frozen; RBAC leakage 0; group role `finance_bi` reads only `finance`). **Next: Phase 3** — Power BI Desktop (owner, guided): install, PBIP project `powerbi/`, the `finance_bi` login, DirectQuery to the views, the 5 pages; done when the dashboard's numbers for 3 weeks = the KPI views. Still open: the owner's review of §8a (G1–G6, PROPOSED).

**Agents plan Phase 1 CLOSED (2026-10-14)** — ADR-046: 40 customers, `vessels.customer_id`, 994 payments (DSO 55 days), a weekly budget (planning model, −11.3 % vs actual), the `finance_test` copy with planted errors (answer key outside the database); `invoices.status` is a documented label (it was random); migration 012 applied, `verify_readonly.sql` §17 clean. **Next: Phase 2** (`finance` star views + KPI views, `docs/finance_metrics.md`; metric definitions go to the owner first), and the owner's review of the plan's §8a generation evaluation (G1–G6, PROPOSED). **Agents plan Phase 0 CLOSED (2026-10-12)** — ADR-045 **Accepted** (best-case bound: the two incomplete candidates cannot change the selection). Phase 0 summary (2026-10-10 / 12) — done: 12 packages pinned (ARCHITECTURE §8), `common.SECRET_KEYS` + `.env.example`, 5 reviewed `langchain-skills` (the local skills folder), `pipelines/agents/llm.py`, `LLM_smoke_test.py` (3 providers pass), `.gitattributes` (data files LF: a CRLF checkout had broken the frozen hashes), the ADR-037 data-policy amendment, and the LLM bake-off (`LLM_bakeoff.py`, tasks frozen `ed6723f5…`, 5 / 9 candidates complete) → **ADR-045 Accepted**: Writer / Insight `qwen/qwen3.8-27b` (Groq) + `gemini-3.5-flash-lite`; Tools `gemini-3.5-flash-lite` + `openai/gpt-oss-20b` (Groq). Handoff in the plan.

**The agents phase — a multi-agent platform in two stages** (owner, 2026-10-09; LangChain + LangGraph, LLMs through free APIs chosen by a bake-off): **Stage 1 the Weekly Finance Pack** (a Power BI finance dashboard kept current + the weekly PowerPoint report, Invoice Auditor, human approval), **Stage 2 the Operations Desk** (Route & Cost Advisor: Suez vs Cape; Voyage & Disruption Watch: ETA, weather, alerts). Plan **APPROVED 2026-10-09**: `dev/history/archive/2026-11-01_Agents_plan.md`; start from its "SESSION HANDOFF" (Phase 0: packages, LLM smoke test, bake-off). Decide there: DuckDB (ADR-018), Redis as a shared cache, DirectML for the session lane (ADR-043), a PostgreSQL connection pool.

History of the RAG plan, phase by phase: **Phase 0 done 2026-10-01** (rewrite confirmed, D9–D11 answered; `Provider_smoke_test.py` 4/4 pass: Jina, Voyage, Gemini embeddings + Jina reranker). **Phase 1 done 2026-10-02** (golden set frozen: 40 EN + 24 Egyptian Arabic twins, 9 identifier queries, 8 RBAC cases; `Data/processed/rag/eval/golden_set.jsonl`). **Phases 2 and 4 done 2026-10-08 — Gemini `gemini-embedding-2`, composed unit** (ADR-037; D1 0.912 vs Voyage 0.804, Jina 0.733, after the title / text normalization ADR-041 and with the three-level evaluation ADR-040); vectors in `Data/embeddings/gemini-embedding-2/`. **Phase 3 done 2026-10-02** (`ports-qdrant` 1.19.1, probe all pass, server-side BM25 available). **Phase 5 done 2026-10-08** (`nilegate_docs`: 2,163 points, dense 3,072 + server BM25, payload = chunk rows, idempotent). **Phase 6 done 2026-10-08** (`search_documents` in `pipelines/lib/retrieval.py`: RBAC inside every prefetch, metadata filters, exact dense + optional BM25 / RRF / rerank / shaping, query cache, fail-fast rate policy; RBAC matrix 88 searches, level 3 to the CEO only). **Phase 7 done 2026-10-08 → ADR-038:** defaults = exact dense + Jina rerank (balanced 0.812 → 0.850; hybrid and context shaping rejected by the ADR-040 rule; RBAC leakage 0); query cache in memory (Redis measured, deferred). **Phase 8 done 2026-10-08 (ADR-042 – ADR-044):** documents uploaded at inference time — one company document shape "PortPilot Document v1" (PDF / DOCX, `docs/templates/`), validator + layered injection screening (52 fixtures as expected, 0 false positives on the corpus), conversation-only uploads in memory with a local ONNX embedding lane, `search_documents(..., session=)` returning corpus `results` + labelled `session_results` (baseline unchanged: dense 0.812 / dense + rerank 0.8495), manager promotion through an offline review (self-test 11/11). Session-lane model `BAAI/bge-m3` (hit@3 EN 1.000 / Egyptian Arabic over English uploads 1.000; the owner's pick `llama2-embedding-600m-8k` 0.767 / 0.167, e5-base 0.933 / 0.500), measured after the project moved to `D:\Project` (2026-10-08). Owner decisions 2026-10-08: floor 0.45 (hit@3 EN 1.000 / AR 0.900), DirectML deferred to the API phase. **Phase 9 done 2026-10-08** (close). **Closed 2026-10-01: notebooks → scripts** (ADR-036, `dev/history/archive/2026-10-01_Scripts_and_ingestion_plan.md`): 15 scripts in `pipelines/` (`pipelines/README.md`), refactored (levels A / B) and verified 15/15 on the owner's machine; notebooks in `dev/history/archive/notebooks/`.

**RAG, steps 3–5 (extraction, cleaning, chunking), done per source.** Done for 7 sources: FBL, LPI Methodology, Suez Notes, LPI Connecting to Compete, HbR annual report 2025, the IMO casualty-reporting circular and **the 23 USCG Reports of Investigation (finished 2026-09-27: 1,544 chunks, corpus 2,163)**. **Semi-structured phase DONE (2026-09-27, plan archived as `dev/history/archive/2026-09-27_SemiStructured_MongoDB_plan.md`): MongoDB 8.0.32 holds 1,321,568 AIS positions, 10,534 vessel records and 435 IFTMIN messages (real samples + synthetic data for our 500 vessels), loaded by one idempotent loader (now `dev/build/semi_structured/MongoDB_loader.py`) with a consistency audit against PostgreSQL.** Closed plans in `dev/history/archive/`; reference scripts: `dev/build/rag/USCG_ROI_chunking.py` (template corpora, OCR, incident profiles), `IMO_MSC-MEPC_3_Circ_4_Rev_1_chunking.py`, `HbR_Annual_report_2025_chunking.py`. The unstructured part (chunks), the semi-structured part (MongoDB) and retrieval (Qdrant, 2026-10-08) are closed.

## Status

| Area | Status | Notes |
|---|---|---|
| Docker + PostgreSQL 16.9 / PostGIS 3.5.2 | DONE (closed) | verified 2026-09-23; closed 2026-09-27: container re-created on 127.0.0.1 only, read-only group role (ADR-034) |
| Docker + MongoDB 8.0.32 (`ports-mongo`, 127.0.0.1 only, app user) | DONE | 2026-09-27; privilege check 6/6, feature probe in `dev/db_audit/mongo/` (ADR-027) |
| ports (837), port_connections (19,990) | DONE | verified |
| toll_rate_bands (177) | DONE | verified; how the CSV was extracted from the PDF is undocumented |
| departments (5), roles (3), employees (100) | DONE | verified |
| vessels (500), containers (1,000), invoices (1,000) | DONE | verified; invoices built in PostgreSQL (ADR-013) |
| Migration 001: drop `accepted_currencies` | DONE | applied 2026-09-23 |
| Migration 002: create `documents` | DONE | applied 2026-09-23; filled 2026-09-27 (29 rows, migration 010, ADR-035) |
| Migration 003: drop `employees.status` | DONE | applied 2026-09-23 |
| Migrations 004–005: `vessels.mmsi` (add, fill from the ITU MID table) | DONE | applied 2026-09-27; verify §13 all zero (ADR-028) |
| Migrations 006–009: integrity constraints, FK / GIST indexes, read-only role, comments | DONE | applied 2026-09-27 (ADR-033, ADR-034); negative test 14/14 rejected; `ANALYZE` done |
| Schema snapshot + audit after migrations | DONE | 2026-09-27 (after 009): §13–§15 all zero, 0 errors |
| RAG corpus inventory + `documents` registry | DONE | 2026-09-27: 29 rows (migration 010, ADR-035), equal to `Data/processed/rag/documents.csv` |
| FBL chunking | DONE | 31 chunks |
| LPI Methodology chunking | DONE | 94 chunks; cross-source concat check = 129 rows |
| Suez Notes chunking | DONE | 4 chunks |
| LPI Connecting to Compete chunking | DONE | 69 chunks; 131 units → 113 after dedup against LPI Methodology (18 suppressed, 7 trimmed); cross-source concat = 198 rows; whole-PDF coverage: 2,189 lines, 0 unaccounted; nothing flagged or pending |
| HbR annual report chunking | DONE | 2026-09-26: 352 chunks (347 level 1 / Operations, 5 level 3 / Finance — ADR-021); 602 units → 593 after within-source dedup (9 suppressed, 1 trimmed); 3 source errata excluded (ADR-022); cross-source concat = 550 rows; whole-PDF coverage: 4,151 lines, 0 unaccounted; nothing flagged or pending |
| IMO circular chunking (`MSC-MEPC_3-Circ_4-Rev_1.pdf`) | DONE | 2026-09-26: 69 chunks (all level 1 / Operations); field catalogue (117 fields, 30 option tables / 553 options) in the extracted file (ADR-023); 689 units, 55 by-design repeats kept, nothing suppressed; 2 source errata excluded (ADR-022, one clause-level) + 1 empty option; cross-source concat = 619 rows; whole-PDF coverage: 2,329 lines, 0 unaccounted; nothing flagged or pending |
| USCG ×23 chunking + IMO incident profiles | DONE | 2026-09-27: 23 reports / 580 pages (115 image-only pages OCR'd with RapidOCR, ADR-025); one notebook for the corpus (ADR-024); 3,223 units (23 incident profiles, 407 values traced) → Executive Summary 49 sentences trimmed, 2 units dropped; 1 source erratum excluded (ADR-022); 1,544 chunks, all level 1 / Operations (figure captions kept as metadata, 2026-09-27); roles in curated text (ADR-026); cross-source concat = 2,163 rows; coverage: 18,999 lines, 0 unaccounted; open points closed as ADR extensions |
| Notebooks → scripts (ADR-036) | DONE | 2026-10-01: 15 scripts + 12 checkpoint `.md`; verified 15/15 locally after conversion and again after the D3 refactor (levels A / B); notebooks archived; plan archived |
| Documents uploaded at inference time (parse → chunk → embed → retrieve, access-controlled) | DONE | 2026-10-08, RAG plan Phase 8 (ADR-042 – ADR-044): `pipelines/lib/upload_reader`, `screening`, `uploads`, `local_embeddings`, `session_store`; scripts Upload_fixtures / Upload_validation / Upload_eval / Upload_promotion; local model `BAAI/bge-m3` (hit@3 EN 1.000 / Egyptian AR 1.000 before the floor); floor 0.45, DirectML deferred (owner, 2026-10-08) |
| Embedding model choice + corpus vectors | DONE | 2026-10-08: **Gemini `gemini-embedding-2`** (ADR-037: D1 0.912 vs Voyage 0.804, Jina 0.733; AR hit@10 0.875); D5 = composed unit `title + newline + text`; vectors `Data/embeddings/gemini-embedding-2/` (2,163 × 3,072, manifest in git). Earlier: | bake-off on the frozen golden set (2026-10-02): Jina 0.754, Voyage 0.825 (mean R@10 en / ar); Gemini 991 / 2,163 chunks, blocked by its free daily quota until the next runs |
| Qdrant container `ports-qdrant` (1.19.1, pinned, 127.0.0.1, API key) | DONE | 2026-10-02: probe all pass (`dev/db_audit/qdrant/`), server-side BM25 available (D4) |
| Qdrant collection `nilegate_docs` (load) | DONE | 2026-10-08: 2,163 points / 29 documents, verified against the files, second load = no change (`Qdrant_loader.py`) |
| `search_documents` (RBAC-filtered retrieval, metadata filters, query cache, rate policy) | DONE | 2026-10-08: `pipelines/lib/retrieval.py`, validated by `Retrieval.py` ✅ 6/6; exact search (IVF / HNSW measured, no gain at this size) |
| Retrieval evaluation (dense / hybrid / rerank / shaping) | DONE | 2026-10-08: ADR-038 (dense + rerank, balanced 0.850; `results_2026-10-08.json` is the baseline for the agents phase) |
| Migration 011: `documents.ingested_at` | DONE | applied 2026-10-08 (audit `dev/db_audit/postgres/2026-10-08_after_011_report.txt`, 0 errors; `Documents_registry.py` ✅): all 29 rows = 2026-10-08 16:58:18+03 (the last full `Qdrant_loader` run); `verify_readonly.sql` §16 expects 29 ingested; `Documents_registry.py` asserts it |
| RAG retrieval plan close (Phase 9) | DONE | 2026-10-08: plan archived; docs updated; bake-off vectors moved out of `_scratch`; rejected local models removed |
| MongoDB + AIS/EDI profiling, generators, loader | DONE | 2026-09-27: `Notebooks/semi_structured/` (profiling 28 cells, AIS generator 22, EDI generator 16, loader 32; all 0 errors); 1,321,568 / 10,534 / 435 documents; 0 schema violations, 0 unaccounted records, consistency audit all pass (incl. tracks at sea); idempotent (ADR-029 – ADR-032) |
| Synthetic incidents / synthetic FBLs | PLANNED (optional) | |
| Causal consistency checks (PostgreSQL ↔ AIS ↔ incidents ↔ RAG) | PLANNED | needs a shared event timeline per vessel/shipment |
| Agents (Supervisor + Analytics) | DONE (2026-11-01, Agents plan archived; label fixed 2026-11-22) | Agents plan Phase 0 CLOSED 2026-10-12 (packages, `pipelines/agents/llm.py`, LLM bake-off → ADR-045); Phase 1 CLOSED 2026-10-14 (finance data, migration 012, ADR-046); Phase 2 CLOSED 2026-10-14 (`finance` views, migration 013, ADR-047); Phase 3 CLOSED 2026-10-15 (Power BI dashboard, ADR-048); Phase 4 CLOSED 2026-10-19 (Stage 1 tools + skills, ADR-049; migration 015; `Tools_check.py` 8 / 8); Phase 5 CLOSED 2026-10-19 (`weekly_pack` workflow + PostgresSaver + approval, ADR-050; migration 016; `Weekly_pack_check.py` 7 / 7); Phase 6 CLOSED 2026-10-19 (PortPilot PPTX, slots, Validator v2 + V8, ADR-051; `Deck_check.py` 4 / 4, 100 / 100 planted numbers caught); Phase 7 CLOSED 2026-10-20 (evaluation: golden weeks, finance Q&A agent, migration 017, ADR-052 / ADR-053; D7 not met, closed by the owner; c3 accepted 2026-10-22 as the baseline, tuning stopped); Phase 8 CLOSED 2026-10-22 (scheduled pack, retention, LangSmith, ADR-054; `Scheduler_check.py` 6 / 6); Stage 1 checkpoint PR merged 2026-10-27; Stage 2: Phase 9 CLOSED 2026-10-27 (tools, ADR-055 / 056), Phase 10 CLOSED 2026-10-27 (`route_advice`, ADR-057), Phase 11 CLOSED 2026-10-28 (`voyage_watch`, ADR-058), Phase 12 DONE 2026-10-30 (the supervisor, ADR-059; Stage 2 done-when met, `stage2_eval_2026-10-30_c1.json`); next D-P12-7, then the one Stage 2 commit; ADR-012; the document tool exists (`search_documents`, untrusted-upload contract in `docs/RETRIEVAL_FLOW.md` §2.1) |
| API, auth, audit_log, guardrails | DONE (2026-11-05) | FastAPI plan archived `dev/history/archive/2026-11-05_FastAPI_plan.md`; ADR-064 (the API: login, runs + SSE, uploads, packs, route advice, the watch, the shared quota) and ADR-065 (conversation memory); `audit_log` in schema `api` (ADR-014 note); Redis / a queue / OpenTelemetry not needed now (ADR-018 note, triggers recorded); the event contract for the frontend is in the archived plan §5 |
| Frontend (web UI) | DONE 2026-11-16 (plan archived; local-stack E2E 15 / 15, leakage 0) — F1 closed 2026-11-06, **concept v2 approved by the owner** (D-FE-3; D-FE-6: English UI, answers in the question's language, blue / white, shadcn/ui; D-FE-7 approved: the Power BI pages in the web, phase F5b); **F2 done 2026-11-06** (sign in, the shell from `/me`, API status, sign out, 404; auth E2E on a mock API); **F0 + F0b + D-FE-1 done 2026-11-07** (every API response typed, the event union, number spans, `/finance/*` reads, `--fake-roles`; `Api_check.py` 12 / 12, ADR-064 note); **F3 done 2026-11-07** (Ask on assistant-ui: SSE runs, number receipts, history, uploads; Playwright 39); **F4 done 2026-11-07** (pack review slide by slide, the decision panel, the request box of D-FE-9, the report; Playwright 67); **F5 done 2026-11-07** (Charts on Recharts: words or catalogue, ask-back; the pack's chart variants and analysis editor; Playwright 71, real-API smoke 5 / 5); **F5b done 2026-11-07** (the six Power BI pages + Smart View + this week's pack in `/finance`; W15 live = the deck; Playwright 75, real-API smoke 7 / 7); **F6 done 2026-11-08** (`/routes` Suez | Cape decision with receipts + earlier advice, `/voyages` radar list + the run's brief + runs, the React Flow view of a pack decision run; Playwright 84, green three runs in a row, real-API smoke 13 / 13); **D-FE-10 + F7 done 2026-11-08** (watch runs: the ADR-006 identity check; the ETA board from the run's rule ETAs — no schedule ETA exists, ADR-055; `compose.yaml` web service via `host.docker.internal`, real-API smoke against the container 14 / 14; security E2E: inert markup, no request out, every page CSP + headers + axe 0; Lighthouse / timings recorded; ADR-060 amendment 3, ARCHITECTURE, THREAT_MODEL web table); **next:** the owner's checks (the real Monday pack decided through the UI 2026-11-09, real-model EN + Arabic questions + one route advice, one week vs Power BI, CI green), then archive + + the owner's one commit | `dev/history/archive/2026-11-16_Frontend_plan.md` (APPROVED 2026-11-06): `web/` scaffold (Next.js 16.4.2, pinned), BFF (cookie session, CSRF, OpenAPI allow-list), CSP with a nonce, `web/design/MASTER.md` v2, three concept screens at `/concept`, tools of §9a reviewed and installed, CI `web` job, `npm run check` ✅; next: the owner approves the look, then F0 (after the approver plan) and F2. Earlier scope: **React / Next.js + TypeScript (ADR-060)**; chat = assistant-ui on a custom runtime over our SSE, candidates Tailwind + shadcn/ui, TanStack Query + Orval, React Flow; local development tooling reviewed first (ADR-060 amendment 1); after the API, free / open-source only, its design in its own plan; security from ADR-060: model text rendered as text / sanitized Markdown (no raw HTML, CSP), CORS for the UI only, CSRF if cookies, a TypeScript client generated from the API's OpenAPI; ESLint + `tsc` in the CI, Dependabot on npm. Must cover: login + the asker's role (RBAC stays in the API, never in the browser); Ask with streamed answers and partial answers shown as such; the weekly-pack approval screen (the LangGraph interrupt: approve / edit / reject, today `Weekly_pack.py resume`); route advice and voyage-watch alerts; deck (PPTX) download; Arabic RTL + English; the LangSmith link per answer for the owner. Power BI stays Desktop (embedding needs a paid licence; "publish to web" is public → not for company data); finance charts in the UI, if any, read the same `finance` views. Tests: Playwright end-to-end (free); a service in Docker Compose |
| Evaluation (golden tasks), observability (trace IDs) | DONE (label fixed 2026-11-22) | Stage 2 evaluation DONE 2026-10-30 (ADR-059, `Stage2_eval.py`, baseline c1); Sentry 2026-11-02 (ADR-062); Stage 1 evaluation DONE 2026-10-20 (ADR-053: golden weeks + finance Q&A, `Stage1_eval.py`; D7 not met, owner closed); observability for the agents DONE 2026-10-22 (LangSmith, ADR-054); API trace ids with the API |
| Scheduled weekly pack + checkpoint retention | DONE | 2026-10-22, Agents plan Phase 8 (ADR-054): Task Scheduler (Monday 10:30), `Weekly_pack.py scheduled / prune / report`, `Scheduler_check.py` 6 / 6 |
| Power BI integration | DONE (2026-10-15) | ADR-048: `powerbi/PortPilot_Finance.pbip` (Desktop, PBIP in git), DirectQuery on the `finance` views via the read-only login `ports_bi`; 5 pages (Exceptions = placeholder until the Auditor tool, Phase 4 / 7); numbers = `kpi_weekly` for weeks 5 / 23 / 49 |
| Docker Compose for all services | DONE (2026-11-17) | `deploy/compose.yaml`: every service (stores, API, scheduler, web, Caddy) for staging / production, ADR-071; rehearsed locally; the cloud VMs are owner steps (`docs/deploy/RUNBOOK.md`) |

RAG ingestion order (do not skip ahead): inventory → metadata → extraction → cleaning → chunking → embedding model → Qdrant (local Docker) → collection → small controlled subset → retrieval test → metadata filtering → RBAC → scale → hybrid/reranking only if evaluation shows it is needed.

## Missing work

**Required**
- ~~Agents phase~~ DONE 2026-11-01 (both stages; plan archived): `dev/history/archive/2026-11-01_Agents_plan.md` (APPROVED 2026-10-09) — Stage 1 Weekly Finance Pack (synthetic finance data: customers, payments, weekly budget; `finance` star views; Power BI Desktop + DirectQuery; the LangGraph pack with Validator and approval), Stage 2 Operations Desk (route advice, voyage watch). Design of the question flow in `docs/RETRIEVAL_FLOW.md`.
- ~~RAG retrieval (embeddings, Qdrant, RBAC-filtered search, evaluation)~~ DONE 2026-10-08 (plan archived).

**Owner actions** — done 2026-09-28: the read-only login user exists (`db/check_readonly_user.py` 8/8 PASS); the orphan Docker volume was deleted.

**Embedding readiness (checked 2026-09-28, read-only):** 2,163 chunks, 16 columns, unique `chunk_id`; 0 empty texts, 0 `char_count` mismatches, 0 over 2,000 chars, 0 under 50, 0 duplicate texts; levels 1 (2,158) / 3 (5); every department in `departments`; every chunk file name in `documents` and every `chunk_count` equal. Nothing blocks the embedding phase.

**Recommended (PROPOSED)** — the former list (CHECK constraints, toll band UNIQUE, FK and GIST indexes, read-only role, vessel type ↔ category link) was applied on 2026-09-27 (migrations 006–007, ADR-033 / ADR-034). Nothing is pending on the PostgreSQL schema.

**Deferred (ADR-018): check at the start of each phase**
- ~~Stabilization Phase 5~~ closed 2026-11-17 by the Staging readiness plan: the restore drill of the three stores
  passed (every count and digest equal, `Backup.py drill`), and the route latencies were measured on the staging
  rehearsal (plan §8); nothing asked for tuning. The 9-point concurrency list below was already met by the FastAPI
  plan (each point → its file in the Staging readiness plan §3 c1–c9).
- DuckDB as the analysis sandbox: the agents phase closed without needing it (its tools read the `finance` views); stays deferred (ADR-018).
- Redis as a shared cache — decided for the API phase: not now (ADR-018 note 2026-11-04, triggers: a second API process, runs that must survive a restart, lock latency > 20 ms p95); originally (query vectors, reranker results, sessions) if several workers or agents must share it; measured 2026-10-08: Redis GET 0.57 ms vs in-process 0.2 µs (ADR-038; owner: use it later if needed).
- A job queue and object storage (MinIO): not now (ADR-018 note 2026-11-04; ADR-071 keeps the triggers: one host, one API process; uploads memory-only, ADR-043).
- ~~**API phase → concurrency requirements (owner, 2026-10-25)**~~ met by the FastAPI plan (2026-11-05; each point → its file in the Staging readiness plan §3 c1–c9), kept as written: Today
  every run is one process (the scheduled pack's lock file, Task Scheduler "IgnoreNew"), so per-process state is
  safe; several FastAPI workers break that. The design must cover, each with a check:
  1. **Daily quota** (`llm_cache/usage.json` is per process: two workers reading 499 both send) → one shared,
     atomic counter (PostgreSQL `UPDATE … RETURNING` or Redis `INCR`).
  2. **Per-minute limits** (`llm.py` `Budget` counts per process) → a shared rate limiter (token bucket); excess
     requests wait in a queue instead of failing.
  3. **Reply / tool caches** (JSONL files with one writer today) → a store safe for concurrent writers (PostgreSQL
     table or Redis), keeping replay determinism (a cached reply never expires).
  4. **The same question at the same moment** → single-flight (one model call, the others wait for its reply).
  5. **The same conversation twice at once** (two requests on one LangGraph thread) → a per-thread lock.
  6. **Database connections** → pool size × workers below PostgreSQL `max_connections` (100 by default).
  7. **Long work** (a weekly pack takes minutes) → never inside an HTTP request: a job queue, `202` + job id, a
     background worker.
  8. **Back-pressure** → `429` / `503` with `Retry-After` when the quota or the queue is full, never a crash.
  9. **Sync code under async FastAPI** (psycopg / httpx / LLM calls are blocking) → a threadpool or async clients.
  Already safe: tools are stateless (the user comes from `RunContext` per request, never a global), pools are
  bounded, checkpoints live in PostgreSQL. Free first: PostgreSQL for the counter and locks; Redis only if a
  measurement shows the need (the trigger of the line above). Proof: a load test with fake models (e.g. 50
  simultaneous requests) — exact counter, no corrupted file, no cross-user data, excess refused with 429.
- ~~Power BI phase → decide on star-schema views~~ decided: plain views in schema `finance` (ADR-047), used by Power BI (ADR-048).

**Blocked**
- Nothing (agents were blocked on retrieval until 2026-10-08).

## Known issues

- Retrieval at query time (2026-10-08): the Jina reranker adds ~0.6–1.5 s and Jina publishes no rate limits (429 seen; graceful fallback to the dense order after 5 s); each question opens a PostgreSQL connection for the user's access (~18 ms; pool in the API phase); Gemini's free tier allows ≈ 1,000–1,450 texts a day (corpus re-embedding needs two days; the free tier trains on inputs, so only public / synthetic text is embedded, ADR-037).
- Re-running `Embedding_bakeoff.py`, `Lib_selftest.py`, `Retrieval.py` and `Search_index_benchmark.py` without API calls needs the git-ignored bake-off vectors in `Data/embeddings/bakeoff/` (moved there from `dev/_scratch/` on 2026-10-08); a fresh clone re-embeds (quota above). Decided 2026-11-17 (Staging readiness plan d5): evaluation-only, never read at runtime, not deployed; the owner's local copy stays the source.
- Jina publishes no rate limit: accepted 2026-11-17 (d4) with the existing 5 s fallback to the dense order; a paid Jina key is the upgrade path.

- ~~`dev/tools/nb_to_script.py check` reports 6 FAILED~~ closed 2026-11-17 (it had grown to 10 FAILED: the scripts changed after the conversion through reviewed edits — the ADR-041 phase, the ADR-063 lint fixes, the D-H2 LF writers): `check` now accepts a script whose statements and checkpoint equal the hashes of its last recorded review (`dev/tools/nb_to_script_evolved.json`, `nb_to_script.py evolve`); any later edit fails until reviewed and recorded again. `check` → ALL OK.

- ~~USCG dedup labels depended on `PYTHONHASHSEED`~~ closed 2026-10-01: when two units covered an Executive Summary sentence equally, `covered_by` followed set / hash order (decisions — 49 trimmed, 390 restated — never changed; chunks unaffected). Fix (owner option A): ties go to the earliest sentence in report order (listed patch in `dev/tools/nb_to_script.py`). The regenerated `USCG_ROI_logical_units.json` (3 labels: MICHIPICOTEN u0089→u0082, u0091→u0084, u0094→u0087, each the analysis section instead of the conclusion) is committed; it now reproduces under any seed. `run.py --hashseed 1` / `2` showed no other hash-order dependence.
- Closed 2026-11-17 (Staging readiness plan d2): the cause is Faker's own platform branch — `_rand_seconds` uses `randint` on Windows and `uniform` elsewhere, so the random stream parts at the first hire date; the script now pins the Windows branch on every platform (`_pin_faker_dates()`), the Linux probe reproduces `employees.csv`, the Windows run is unchanged. The original report, kept as written: `SyntheticGenerator` (notebook and script alike) does not reproduce `employees.csv` on Linux (cloud session, 2026-10-01): hire dates and then names differ from the first draw, with the same Faker 40.38.0, seed, reference date and with TZ=Africa/Cairo. On the owner's Windows machine the script passes (2026-10-01, `files changed: 0`), so the generator is reproducible there but not across platforms. Not caused by the conversion (the original notebook fails at the same cell on Linux).
- ~~Guard hook untested on Windows~~ closed 2026-10-01: a Read of an archived `.ipynb` was blocked in an assistant session on the owner's machine. The guard hook path is now the local guard hook (a relative path blocked every command once the shell changed directory); to confirm it still runs on the owner's Windows setup (the local script runs went through PowerShell, so they do not test it).
- ~~Git: the USCG WIP~~ stale since every phase was committed (the history was rewritten 2026-11-19, ADR-072). Kept as written: Git: the USCG WIP up to Phase 4 is committed (e89ef95); the finished notebook, its three artifacts (extracted, cleaned, chunks) and the 2026-09-27 docs (archive, ADR-024–026, ARCHITECTURE, ROADMAP) are to be committed by the owner. Seen from the Linux VM, several data files show as modified only because of CRLF line endings (no content change).
- Cleaned-file format differs by source: LPI Connecting to Compete and HbR store `{source, units, duplicate_audit, coverage_audit}`, older sources store a plain list of units. Not blocking: the embedding phase reads the chunk parquet files (one schema), not the cleaned files.
- The old DB password was committed in notebooks before ADR-015 (local development container only). 2026-11-17: never reused outside the owner's machine — every deployment environment gets fresh credentials (`ops/deploy/new_env.py`, `Backup.py secure`); the local rotation and the history scan are owner steps (`docs/deploy/RUNBOOK.md` §10–§11; the local superuser password is also the dictionary word `postgres`).
- `Notebooks/synthetic/SyntheticGenerator.ipynb` was fixed on 2026-09-23 (paths, `%pip`, currencies, indentation, `rate_sdr_per_ton`, date anchoring, validation cell) and on 2026-09-27 (ADR-017 drift, database-owned `mmsi`). Re-running it reproduces employees, vessels and containers exactly (28/28, re-checked after the PostgreSQL container was re-created).
- ~~The notebooks have no automated tests.~~ The notebooks are archived (ADR-036); the scripts and checks run in CI (ADR-063). Validation lives in assertion cells.
- Done (ADR-035 `documents`, the per-chunk payload in `nilegate_docs`): `sensitivity_level` / `department` vary within one source (HbR, ADR-021): the future `documents` rows and the Qdrant payload must carry them per chunk; a document-level value is not enough.
- `toll_rate_bands.csv` extraction method is undocumented (the never-run `ExtractTollRates.ipynb` probe was deleted on 2026-09-27).
- ~~`pymupdf4llm` unused dependency~~ removed 2026-09-27 (`uv remove`; also drops pymupdf-layout and tabulate, used nowhere).
- Semi-structured phase (2026-09-27), open points:
  - ~~Synthetic AIS routes crossing land~~ closed 2026-09-27: sea paths per leg (`searoute`), open-sea fixes on land 49 % → 0.96 % (canals and narrow waterways only); MongoDB reloaded (1,321,568 positions), audit all pass (ADR-032 amendment).
  - EDI ↔ invoices: linked 2026-09-28 by owner decision (`RFF+IV` = the vessel's latest invoice, 376 messages; the flow is mimicked, dates are not aligned; audited, `edi_invoice_mismatch = 0`; ADR-032 amendment 2).
  - Our `imo_number` / `container_number` are sequential and mostly fail their check digits (kept by owner decision Q-A).
  - ~~`ports-postgres` on all interfaces~~ closed 2026-09-27 (loopback only, ADR-034). ~~Orphan Docker volume~~ deleted by the owner 2026-09-28.
  - `SyntheticGenerator.ipynb` could not have passed before 2026-09-27: it still built `employees.status` (ADR-017 drift). Fixed (draw kept), full run 28/28 with all CSVs identical.
  - ~~Extra load reports from test runs~~ cleaned 2026-10-01: the stale 20260928T111702Z pair was removed from git; each loader run adds one report and only the newest describes the current MongoDB content (its `load_run` is stamped on every document), so keep only the newest.
- Unstructured data closed (2026-09-27): all 7 raw PDF sources are chunked (corpus 2,163); the three USCG open points were closed as recorded decisions (ADR-019, ADR-020 and ADR-023 extensions: letters' restated recommendations kept; raster figures caption_only by rule; profiles code printed facts only). Notebooks reorganised into `Notebooks/rag/`, `structured/`, `synthetic/`; `dev/_scratch/` emptied.
