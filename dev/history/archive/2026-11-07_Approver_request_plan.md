# Plan — the manager asks in words; the pack and the dashboard change together

**Status: IMPLEMENTED (2026-11-07)** — approved the same day (owner: "موافق، اعتمدها").

## Implementation record (2026-11-07)
- **Done when — met.** On the live W15 pack the manager's one request in Egyptian Arabic (a chart + "look again at
  the overdue") came back as what was understood, was confirmed, ran as one revise (the steer + the 8-week Billed /
  Collected trend), waited again; "تمام، اعتمده" approved it; the publisher wrote `run.json` and migration 024's row;
  Power BI's Approved Pack = `GET /finance/pack` (16 values equal) = the deck.
- **Built:** `pipelines/agents/approver_request.py` (the interpreter, the proposal, the step runner); CLI
  `Weekly_pack.py resume --request … [--yes]`; API `POST /packs/{thread}/request` + `/confirm`, `GET /finance/pack`;
  `views.pack_views`; the publisher's `summary` / `approved` + `store_approved`; migration **024** (applied, 0 errors);
  Power BI page **Approved Pack**; checks `Approver_request_check.py`, `Api_check.py` 12 / 12; evaluation
  `Approver_request_eval.py` on a frozen 30-request set: **exact 0.9667 (EN 1.0, AR 0.9333), ask-back 1.0, invented
  numbers 0** (run 3; run 1 0.90, run 2 0.90 kept as `_run1` / `_run2`).
- **Deviations:** D-AR-1 (text edits read again after a re-draft), D-AR-2 (the request as the log comment), D-AR-3 (no
  new SSE event), D-AR-4 (a stateless confirm), D-AR-5 (the week rule before the confirm), D-AR-6 (agent_writer's
  default DML), D-AR-7 (Desktop's bookmark property), D-AR-8 (approve / reject need the manager's word), D-AR-9 (note
  edits pre-checked with the pack's own `apply_analysis`), D-AR-10 (one prompt line: "look again" → a steer only),
  D-AR-11 (approve + changes read as a change). Details in Progress below.
- **Decisions:** ADR-067; ADR-048 am. 3, ADR-050 am. 3, ADR-051 am. 6, ADR-064 / ADR-066 notes.
- **Not done / follow-ups:** the web side (the request box on the approval screen, the "this week's pack" panel on
  `/finance`) belongs to the frontend plan (told to its session); the steered summary may still state figures rather
  than a cause (the Insight model's analysis); `Pack_external_context_plan.md` resumes next (DEFERRED).

Original status line: **APPROVED (2026-11-07, owner: "موافق، اعتمدها")** — written PROPOSED the same day; the owner's request of 2026-11-07: a trigger builds the weekly pack, it is shown
to the manager before it is published, the manager may dislike it and ask for a change **in his own words** (the
analysis, the charts or the text — "كأنك هتاخد منه مجرد prompt"), it is changed and comes back to him, and **the same
change shows on the dashboard**, since the dashboard is shown with the pack ("طبّق نفس الكلام ع الـ dashboard"). No
code before the owner approves this plan. It goes **before** `Pack_external_context_plan.md` (DEFERRED the same day,
owner "تمام"). Touches ADR-050 (approval interrupt), ADR-051 (Validator), ADR-066 (chart catalogue, views), ADR-045
(free quota), ADR-064 (API), ADR-048 (Power BI Desktop), the frontend plan §6.4 / §6.9 (a change to approve there).

## 0. What exists and what is missing (verified 2026-11-07)

| Step | State |
|---|---|
| Trigger (Monday 10:30, Task Scheduler → `Weekly_pack.py scheduled`) | **EXISTS** (ADR-054) |
| Pack built: KPI + audit by code, Insight, Writer with slots, Validator | **EXISTS** |
| Shown to the manager, waits (`interrupt`, preview PPTX, `GET /packs/{thread}`) | **EXISTS** |
| Change the text / add a bullet / change a chart / change the analysis / steer, re-validated, waits again | **EXISTS** — but only as **structured input**: `--add "4: …"`, `--chart '{json}'`, `--analysis file.json`, `--steer`, or the API's `DecisionIn` fields. Checked live on W14 2026-11-07 |
| **The manager writes one request in words → the right change** | **MISSING** — the gap the owner felt ("بنلف في loop") |
| Dashboard: a reader asks in words → a chart (`POST /views {question}`: one call picks from the catalogue, code draws) | **EXISTS** (ADR-066) |
| **The approved pack's changes show on the dashboard** | **MISSING** — `run.json` keeps the chosen charts, nothing shows them on the dashboard; the web dashboard `/finance` itself is PLANNED (frontend plan F5b) |

## 1. Owner decisions (to ask once, as clickable choices, recommendation first)

| # | Question | Recommended | Alternatives |
|---|---|---|---|
| R1 | Where "the same change on the dashboard" shows | **The web dashboard `/finance`**: for a week with a published pack, a "This week's pack" panel shows the approved summary and the manager's charts, drawn from the same rows; Power BI Desktop unchanged (ADR-048: Desktop, choices by click) | + Power BI too: a read-only view `finance.pack_approved` (a migration) and a Power BI page showing the approved summary and chart choice (DAX switch) |
| R2 | When a request is applied | **The system says what it understood, the manager confirms with one click**, then it runs (a misread never changes the pack silently) | Applied at once; the new preview is the confirmation (faster; a misread costs a revise) |
| R3 | A request that mixes the analysis and the text (D1: one kind per decision; D2: a revise starts clean) | **Code runs it in steps**: the revise first, then the text / chart changes on the new draft — one request, one wait | The manager is asked to split it |
| R4 | Acceptance | **A frozen set of manager requests (EN + Egyptian AR) like `Views_eval`**: exact interpretation ≥ 0.90 (AR ≥ EN − 0.10), 0 invented numbers, refusals kept | Fake checks + one live pack only |
| R5 | Commit | **One commit when this plan closes**, separate from C4 | Folded into C4 |

**Owner's answers (2026-11-07):** **R1 = the web dashboard + Power BI** (over the recommended web only); R2 says
what it understood and waits for one click (recommended); R3 code splits a mixed request (recommended); R4 + R5 a
frozen request set + a separate commit (recommended).

## 2. Design (PROPOSED)

### 2a. The request interpreter (`pipelines/agents/approver_request.py`)
- **One structured call** (`tools` role, flash-lite, ADR-045) like `views.choose`: input = the manager's request
  (≤ 500 chars), the draft's slide titles and bullets with their indexes, the Insight notes with indexes, the chart
  catalogue (`deck/charts.py`); output = `ApproverRequest` = an ordered list of **existing** change kinds only:
  `edits`, `additions`, `charts`, `analysis_edits`, `steer` (+ `approve` / `reject` when the request says so), and a
  one-line `understood` in the request's language.
- The model never writes a NileGate number: text edits and additions still go through the Validator (every number
  binds to its slide's evidence, ADR-051); a request it cannot place → an ask-back ("which slide?"), never a guess.
- Code splits the steps (R3): a `revise` step (analysis edits / steer) runs first; the `edit` step (text, additions,
  charts) runs on the new draft; one `approval_needed` at the end. Caps (D3) and the 2-revise limit unchanged.
- The manager's request is his own words (trusted input); the draft text it sees may hold screened web news (slide 9,
  ADR-042 note) — the interpreter's output schema has no free action, only the listed kinds.

### 2b. Where it is used
- **API:** `POST /api/v1/packs/{thread}/request {request}` → 202 run + SSE; the `understood` event first; with R2
  recommended a `confirm` step: `POST /packs/{thread}/request/{id}/confirm` runs it (or the manager rephrases).
- **CLI:** `Weekly_pack.py resume --thread … --as 6 --request "<words>"` (prints what it understood, asks y / n).
- The structured options stay as they are (the frontend's edit panel, §6.4).

### 2c. The dashboard shows the approved pack (R1)
- On `approve`, the publisher already writes `run.json` with `charts`; it adds the approved summary bullets and
  the request log (no new data: texts the Validator passed).
- **API:** `GET /api/v1/finance/pack?week=YYYY-Www` → the approved summary + each chart as a `ViewSpec` drawn by code
  from the same `finance` rows (`charts.build_spec`, the pack's `trend` / `variance`), RBAC as the finance views
  (ADR-006). No LLM.
- **Web (frontend plan, a change to approve there):** `/finance` shows the "This week's pack" panel for that week;
  the reader's own Smart View questions stay personal (they never change the published pack).
- **Power BI (owner R1):** migration `024_pack_approved.sql`, applied by the owner (development rule 2):
  - tables `agent_state.pack_approved_summary (report_week, idx, text, approved_at, approver_employee_id)` and
    `agent_state.pack_approved_chart (report_week, chart, series[], weeks, measure, rows)` — written only by the
    publisher on `approve` (login `ports_agent`: INSERT / DELETE on these two tables only; a re-published week
    replaces its rows);
  - read-only views for `ports_bi`: `finance.pack_approved_summary` and `finance.pack_trend_long (report_week,
    trend_week_label, series, value)` / `finance.pack_variance_long (report_week, vessel_category, measure, value)` =
    the existing `finance` trend / category views **reshaped and filtered** to the approved choice (no new KPI math,
    ADR-047: a long form + a join, every value still a field of those views);
  - a Power BI page **"Approved pack"** (DirectQuery, the week slicer): the approved summary as a table, the trend
    line by `series`, the variance bars by `measure` — the chart follows the manager's choice because the rows do,
    no DAX switch. Built on screen through the modeling tool server and PBIR, each visual's data explained (memory:
    Power BI pages); ADR-048 amendment 3.
  - Same numbers check: the page's values = `GET /finance/pack` = the published deck (V8's read-back), on one week.

## 3. Tests
- `Approver_request_check.py` (fake model, 0 calls): each kind from a scripted reply; a mixed request → revise then
  edit, one wait; an unplaceable request → ask-back; a number not in the evidence → refused by the Validator; caps;
  a request on a pack not waiting → 409; the confirm step.
- `Approver_request_eval.py` (R4): a frozen set (~30: 15 EN + 15 Egyptian AR, frozen before the first run, sha in the
  script like `Views_eval`) of requests on one frozen draft → exact interpretation, ask-back recall, invented numbers 0.
- `Api_check.py`: the two new routes (202 / SSE, 403 outside Finance, 409, 422 shapes); OpenAPI snapshot regenerated.
- No-regression: `Weekly_pack_check.py`, `Deck_check.py`, `Views_eval.py` Phases offline, lint ratchet 0 / 0.
- **Live:** the manager writes one request on a real pack (W15, Monday 2026-11-09, or run early) covering a chart and
  the analysis; it comes back changed; approved; the dashboard endpoint returns the same summary and charts.

## 4. Phases
| Phase | What | Done when |
|---|---|---|
| A | `ApproverRequest` model + the interpreter + the step runner (revise → edit) | fake check passes |
| B | CLI `--request` + API routes + `GET /finance/pack` | `Api_check.py` passes, snapshot regenerated |
| B2 | Migration 024 (owner applies) + the publisher's DB write + the snapshot / `verify_readonly.sql` refresh + the Power BI "Approved pack" page | the page = `GET /finance/pack` = the deck on one week |
| C | Frozen request set + `Approver_request_eval.py` (R4) | gates held |
| D | Docs: ADR-067 (the request interpreter), ADR-050 / ADR-066 notes, `ARCHITECTURE.md`, the frontend plan change sent to its session | written |
| E | The live check | the manager's one request changes the pack and the dashboard shows it |

## 5. Done when
- The manager writes **one request in words** on a waiting pack; it comes back changed (text, chart or analysis) and
  re-validated; he approves; the dashboard's week shows the same approved summary and charts.
- R4 gates held; no number in the pack that the code did not fetch.

## 6. Risks / uncertain
- flash-lite 500 free requests / day: one call per request + a revise's calls; the eval ~30 calls once.
- The web dashboard is not built yet (frontend F5b): until then the web part is the API endpoint + its check; the
  Power BI page shows it first.
- The publisher writing to the database is new (today it writes files only): a failed DB write must not lose a
  published deck — files first, then the rows, and a re-run of the same week replaces its rows (recorded in
  `run.json`).
- A request that asks for something outside the catalogue (a new chart type, a number not in the views) is refused
  with the reason — by design (ADR-066 rejected a free chart spec).

## Progress / deviations
- 2026-11-07 — written PROPOSED; `Pack_external_context_plan.md` marked DEFERRED (owner "تمام": this plan first).
- 2026-11-07 — R1–R5 asked as clickable choices: all as recommended except **R1 = web + Power BI**; §2c gained
  migration 024 + the "Approved pack" page, phase B2 added. Waiting for the owner's approval of the plan.
- 2026-11-07 — **APPROVED** (owner: "موافق، اعتمدها").
- 2026-11-07 — **Phase A done** (new files only, nothing shared edited):
  - `pipelines/agents/approver_request.py`: `ApproverRequest` (the one call's schema: `change` / `approve` /
    `reject` / `ask_back` + the pack's existing kinds; `RequestChart.weeks` an int checked by `ChartChoice` — Gemini's
    string-enum rule), `view_of` (the rendered bullets / notes / charts / evidence ids with their indexes),
    `interpret` (one `tools`-role structured call), `propose` → `Proposal` (understood, steps, ask-back, `draft_sha`),
    `steps_of` (R3: revise first; every step pre-checked by `ApprovalDecision`, a refused shape → ask-back before any
    run), `apply` (each step a `Command(resume=…)`, a refused step stops the rest, stale guard on `draft_sha`).
  - **D-AR-1:** in a mixed request, text edits name bullets of the old draft, which a revise replaces; additions
    (slide + text) carry over, but edits are **read again on the new draft, text only** (one more call) — the plan
    said "the edit step runs on the new draft" without saying how its indexes are found.
  - **D-AR-2:** the request is logged as the approval-log comment (`request: …`, ≤ 500) when no comment is given, so
    `approval.json` shows what the manager asked for.
  - `pipelines/scripts/agents/Approver_request_check.py` Phases 1–2 (fake, 0 calls) passed in 58 s: four kinds →
    their steps; three ask-backs (unplaceable, a 5-week trend, two invalid replies → the fixed Arabic line); a chart,
    an edit + addition, a steer and a mixed request applied (the mixed one as revised → edited with the text read
    again, one wait); stale refused; an unbound number held by the Validator; approve published. ruff / pyright
    clean, lint ratchet 0 / 0.
  - ~~Next: Phase B~~ (done below) edits shared files
    (`Weekly_pack.py`, `pipelines/api/routers/packs.py`, `schemas.py`) that still hold the approver-additions plan's
    uncommitted work → wait for the owner's commit C4 first (R5: a separate commit).
- 2026-11-07 — **Phase B done** (the owner committed C4 first, R5):
  - CLI: `Weekly_pack.py resume --thread … --as <id> --request "<words>"` prints what was understood + the steps;
    `--yes` applies them (the same request on the same draft is a reply-cache hit, so the confirmed run applies
    what was shown); `--decision` is no longer required when `--request` is given.
  - API (`pipelines/api/routers/packs.py`): `POST /packs/{thread}/request` (202 run; the `answer` event carries the
    proposal — **no new SSE event**, D-AR-3: `understood` is the memory event's name, ADR-064's contract unchanged);
    `POST /packs/{thread}/request/confirm` (202 run; **stateless**, D-AR-4: the client sends the proposal back, every
    step re-checked by `DecisionIn` and by the graph — it can hold only what `POST /decision` already accepts from
    this approver; 409 `stale` when the draft changed); run kind `pack_request` (20 / h, 60 s), the confirm runs as
    `pack_decision`. A shared `_decidable()` now serves `/decision` too (same checks, same order).
  - **D-AR-5:** `propose` also checks the catalogue's week rule on this pack (an N-week window needs week ≥ N) —
    found by `Api_check`: an 8-week trend on week 5 passed `ApprovalDecision` and was refused only after the confirm;
    now it is an ask-back before it.
  - Dashboard: the publisher writes `run.json` `summary` (slide 2 as the deck says it) + `approved` (at, approver);
    `views.pack_views()` draws the pack's two charts as views (trend → trend, variance → category, the approved
    variant or the default) as the asker; `GET /api/v1/finance/pack?week=` (a `dashboard` router in `packs.py`,
    registered before `finance.router` so `/finance/{dataset}` does not catch it; `finance.py` not touched — the
    frontend session edits it). A pack published before this change has no `summary` → 404 with the reason.
  - Checks: `Approver_request_check.py` + a window-rule case passed; `Api_check.py` Phase 7 widened (proposal with
    one fake call and nothing applied, a Finance employee 403, a short request 422, the window ask-back, stale 409, a
    wrong step 422, confirm → edited + `approval_needed` + the request as the log comment, then `/finance/pack`:
    the summary, the 4-week trend as the manager chose, 403 / 404 / 422); OpenAPI snapshot regenerated (34 paths);
    ruff / lint ratchet 0 / 0.
  - The web allow-list (`web/`, the frontend session's) must be regenerated from the new snapshot (`npm run
    gen:allowlist`) — told to that session.
  - **Next: Phase B2** (migration 024: the owner applies it; then the publisher's DB write and the Power BI page).
- 2026-11-07 — **Phase B2 started:** `db/migrations/024_pack_approved.sql` written (NOT applied): tables
  `agent_state.pack_approved` (one row per week: approved chart choices with defaults filled, approver, degraded) +
  `agent_state.pack_approved_summary`; views `finance.pack_approved_summary`, `finance.pack_trend_long`,
  `finance.pack_variance_long` (reshape + filter of kpi_weekly / kpi_weekly_category, the deck's window and row
  rules); grants through 016 / 013 default privileges (**D-AR-6:** agent_writer gets 016's SELECT / INSERT / UPDATE /
  DELETE, not only INSERT / DELETE). Source columns checked in the snapshot.
  **Next:** the owner's yes → apply 024 + snapshot + verify_readonly; then the publisher's DB write (only when
  dataset = live and reports_dir = the real `reports/`, so checks with temp folders never write; files first, rows
  after, a failure logged not raised); then the Power BI "Approved pack" page; then Phases C–E.
- 2026-11-07 — **Migration 024 APPLIED** (owner: "أيوة، طبّقها"), 0 errors; grants as designed (agent_writer DML on
  the two tables; finance_bi + ports_readonly SELECT on the three views); `ANALYZE`, snapshot refreshed,
  `verify_readonly.sql` 0 errors (`db/audit/2026-11-07_after_024_report.txt`); `db/README.md` row added.
  - Publisher: `store_approved()` after the files (live dataset + the real `reports/` folder only, `is_live_reports`);
    a failure is logged as a WARNING (Sentry) and recorded as `published.db_rows`, never raised.
  - W14 (approved this morning, before the change) stored once from its thread with the same function: the views =
    `views.pack_views` (trend 26 values, variance 13 categories, equal); `Approver_request_check` (temp folder: no
    row written) and `Scheduler_check.py` 6 / 6 passed; ruff / pyright clean.
  - **Next:** the Power BI "Approved pack" page (Power BI Desktop open with PostgreSQL running; modeling tool server +
    PBIR; each visual explained), then Phases C–E.
- 2026-11-07 — **Power BI "Approved Pack" page built** (Desktop closed while the files were written, as D-G2; then
  reopened by the owner, port 57112):
  - **D-AR-7:** on reopening, Desktop refused the report: the three Smart View bookmarks it saved on 2026-11-06 hold
    `options.preserveNewVisualVisibility`, which their declared bookmark schema 2.1.0 does not allow. The line was
    removed from the three files (the option only governs visuals added after a bookmark; the bookmarks' behaviour
    on Smart View is unchanged).
  - Model (TMDL): tables `Approved Summary` / `Approved Trend` / `Approved Variance` (DirectQuery on the 024 views,
    `report_week` hidden, each `-> Week`), measures `Approved Trend Value` / `Approved Variance Value` (SUM of the
    view's value: no KPI math, ADR-047); `model.tmdl` refs.
  - Page `b8d4f6a2c3e5d7f9a1b2` "Approved Pack" (8th): title, the synced week slicer (a copy of Smart View's),
    the summary table (line_no, text), the trend line chart (trend_week_label × series_name), the variance bar chart
    (vessel_category, descending = the deck's order top-down). Plain visuals: the chart follows the manager's choice
    because the view's rows do.
  - Checked through TMDL editing on W14: 5 summary lines, 26 trend values, 13 categories; W14 billed
    4,132,083.68 and the variance sum −1,471,958.82 = SQL = `GET /finance/pack` = the deck.
  - Open: the owner picks 2025-W14 in the slicer, looks at the page, then saves (Ctrl+S) — until then the bookmark
    fix and the page are on disk but Desktop's own save may rewrite them in its format.
- 2026-11-07 — **The page saved  on screen** (owner: "اعملها انت"): Desktop reopened from the .pbip with no
  issues dialog; week slicer set to 2025-W14 (now the page's default), the three visuals drawn (the five approved
  summary lines, Billed / Budget W02–W14, 13 categories by billed − budget), saved 14:21. **D-AR-7 (cont.):** the
  owner's earlier close at 13:51 had saved and re-written `preserveNewVisualVisibility` into the three bookmarks
  (the published bookmark schema 2.1.0 does not define it; 2.2.0 does not exist — a Desktop mismatch); removed
  again before reopening; the 14:21 save kept them clean. If the "issues" dialog comes back after a Desktop save,
  remove that one line from `bookmarks/*.bookmark.json` (Continue also opens the report).
  - **Next: Phase C** (the frozen manager-request set + `Approver_request_eval.py`), then D (ADR-067, docs), E (a
    live request on a real pack).
- 2026-11-07 — **Phase C done.** Frozen before the first real run: `approver_request_golden.jsonl` (30 requests, 15 EN
  + 15 Egyptian AR: charts, additions, edits, analysis edits, steers, mixed, approve / reject, ask-backs; sha16
  2ddd0d07c4415147) and `approver_request_draft.json` (W14's draft / notes / evidence from its thread, which the
  30-day retention deletes; sha16 a16be270c9678135). `Approver_request_eval.py`: Phase 1 offline (shapes + SHA),
  Phase 2 real (`tools` role, 37 calls on flash-lite, cached after).
  - **Result:** exact **0.90** (EN 0.8667, AR 0.9333 ≥ EN − 0.10), ask-back recall 1.0, invented numbers 0 → R4 gates
    held (at the edge). Wrong: r07 (a steer + an unasked summary edit), r15 (two invalid replies → the fixed
    ask-back), r22 (an Arabic "look again" read as **approve**).
  - **D-AR-8:** approve / reject now need the manager's own word for it (`APPROVE_WORDS` / `REJECT_WORDS`, EN + AR);
    otherwise code asks back ("عايز تعتمد الـ pack زي ما هو؟") — the model alone never ends a review. Re-scored from
    the cache: r22 is now an ask-back (still counted wrong: a steer was expected), exact 0.90 unchanged; the check
    gained the case (`Approver_request_check.py` passed). `approver_request_eval_2026-11-07.json`.
  - **Next: Phase D** (ADR-067 + notes on ADR-050 / 051 / 064 / 066 / 048, `ARCHITECTURE.md`, `docs/THREAT_MODEL.md`
    — the request as an LLM01 surface, `pipelines/README.md`, ROADMAP), then E (a live request on a real pack).
- 2026-11-07 — **Phase D done (docs):** ADR-067 (new) + ADR-048 amendment 3 (the Approved Pack page, the bookmark
  note D-AR-7), ADR-050 amendment 3 (the request path, the publisher's rows), ADR-051 amendment 6 (the Validator
  still binds the interpreter's texts), ADR-064 note (the three routes), ADR-066 note (`pack_views`);
  `ARCHITECTURE.md` (§4 the migration 024 paragraph, §7 the routes, §9 row 067, the Power BI row);
  `docs/THREAT_MODEL.md` (LLM01: the request as a third surface, D-AR-8); `pipelines/README.md` (the check, the
  eval, `--request`); `docs/ROADMAP.md` current phase; the project rules current-phase sentence; `db/README.md` row 024.
  - **Next: Phase E** — a live request on a real pack (W15): the manager writes one request covering a chart and the
    analysis; it comes back changed; approved; `GET /finance/pack` + the Power BI page show the same. Then the
    implementation record, the archive and the commit (R5); after the commit.
- 2026-11-07 — **Phase E done (live), W15 run early at the owner's request** (`weekly_pack:live:2025-W15:1`, the
  scheduler's next week; DEGRADED by the fallback: bullets 6 and 7 dropped). The manager's request, in Egyptian
  Arabic: "اعرض المفوتر والمحصّل على 8 أسابيع في رسمة الـ trend، وبص تاني على سبب تغيّر المتأخرات الأسبوع ده".
  - **Attempt 1:** understood right, but the proposal added an unasked summary edit whose two numbers were kpi.weekly
    fields cited as kpi.overdue → the graph refused the whole revise after the confirm (logged with the reason; the
    pack unchanged). **D-AR-9:** `propose` now runs the pack's own `apply_analysis` on the waiting notes, so such a
    note becomes an ask-back before the confirm. **D-AR-10:** one prompt line — "look again / investigate / explain"
    → a steer only; analysis edits only when he dictates a note.
  - **Eval run 2** (the prompt changed: 36 new calls): exact 0.90 (EN 0.9333, AR 0.8667); r07 / r22 now came back as
    `approve` + a steer, twice invalid → the fixed ask-back. **D-AR-11:** an approve / reject that carries changes is
    read as `change` (a before-validator; ending a review still needs the manager's word, D-AR-8). **Run 3** (re-scored
    from the cache): exact **0.9667** (EN 1.0, AR 0.9333), ask-back recall 1.0, invented numbers 0; the one miss r28 did
    less than asked (one series and the addition left out — visible in "understood" before the confirm). Run 1 and 2
    kept as `approver_request_eval_2026-11-07_run1.json` / `_run2.json`.
  - **Attempt 2:** proposal = one revise (steer "إيه سبب تغيّر المتأخرات الأسبوع ده؟" + the trend Billed / Collected over
    8 weeks), no extra note → applied (`revised`), the variant kept, waiting again; then "تمام، اعتمده" → `approve`
    (the word guard passed) → published `reports/2025-W15/`; the publisher stored the row by itself
    (`agent_state.pack_approved` W15: billed_sdr + collected_sdr, 8 weeks); Power BI (DAX through the model tooling) = what
    `GET /finance/pack` draws: 16 values W08–W15 equal; W15 billed 3,767,281.17 = the deck. The steered summary still
    states the overdue figures rather than a cause — the model's analysis, not a mechanism fault.
  - Consequence: Monday 2026-11-09's task builds W16.
