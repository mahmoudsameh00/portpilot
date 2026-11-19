# Plan — the weekly pack's external context fetched by code, not left to the Insight model

> **Status: IMPLEMENTED (2026-11-09)** — closed in the traffic-billing link plan's session (owner: "قفّل خطة السياق
> وكمّل الربط").
> - **What changed:** a deterministic node `external_context` (`audit → external_context → insight_llm`) fetches the
>   week's Suez transits and news by code, with every outcome and reason recorded. The digest, the prompt line, the
>   evidence ids `context.*`, `SLIDE_EVIDENCE[9]`, the `run.json` field and the transit-week summary (D-EC-4) follow.
>   The Insight keeps its tools for drill-downs (E2).
> - **Results:** Phase B checks pass. Phase C candidate **ec2 kept**: every ADR-052 gate held in both runs; narrative
>   recall 0.948 vs c5b's 0.931. Phase D: ADR-050 amendment 4, ADR-051 amendment 7, `ARCHITECTURE.md`; the two skill
>   lines were reviewed by the owner on 2026-11-08. Phase E: the live **W16** pack (`weekly_pack:live:2025-W16:4`)
>   shows slide 9 with the code's transit line (mean 35.6, quietest 28 on 04-15, busiest 45 on 04-18) and two news
>   lines; **the Insight called no tool**.
> - **Deviations:** D-EC-1 (fake models get `no_context`), D-EC-2 (its own check script), D-EC-3 (Phase C restarted
>   after the skill edits), D-EC-4 (code's week summary + `context.` slots), **D-EC-5** (evidence ids with a `[row]`
>   are normalised; W16:1 / W16:2 had ended `output_invalid`) and **D-EC-6** (the code draft's slide 9 uses that
>   summary instead of "External context unavailable").
> - **Checks after the fixes:** `Weekly_pack_check` 9 / 10 (Phase 5 = real models, on request), `Deck_check` 8 / 8,
>   `External_context_check` and the lint ratchet clean.
> - **Open for the owner:** W16:3 (it has the old "unavailable" line) and W16:4 both await approval, so reject W16:3
>   and review W16:4. There is no commit yet; the commit note below still applies.

**Status: APPROVED (2026-11-08, owner: "موافق، ابدأ")** — resumed 2026-11-08 (owner: "من غير commit كمل") — written 2026-11-07 after the W14 finding below
(owner: "أيوة، اكتب الخطة"), deferred the same day behind the approver-request plan (closed 2026-11-07, ADR-067);
decisions E1–E5 already answered (§1). No code before the owner approves this plan. `docs/plans/` also holds
`Frontend_plan.md` (another session). **Commit note:** this plan edits `pipelines/agents/graphs/weekly_pack.py`,
which still holds the approver-request plan's uncommitted changes (the owner chose to continue without a commit):
E5's separate commit is then only possible if the owner commits the approver-request work first; otherwise both
plans land in one commit.
Touches ADR-050 (the `weekly_pack` graph), ADR-051 (the deck, slide evidence), ADR-052 (acceptance rule), ADR-045
(free quota), ADR-042 note / `untrusted-content` skill (web text is untrusted).

## 0. What happened (existing, verified 2026-11-07)

- W14 (`weekly_pack:live:2025-W14:1`, published 2026-11-07) has slide 9 = "External context unavailable".
- **Cause:** the Insight agent (gemini-3.5-flash-lite) called only `invoice_audit` and never called `suez_transits`
  or `web_search`. The tools themselves work: a direct call the same day returned Tavily news (2 rows) and PortWatch
  W14 transits (7 rows). The earlier guess "Tavily credits used up" was wrong.
- W12 and W13 (both runs) did call both tools. The prompt (`INSIGHT_TASK`) only *allows* them ("Use your tools only
  for what is not there … external context …"), so calling them is the model's choice, week by week.
- Nothing flags it: the Validator checks the numbers that are there, not context that was never fetched; `run.json`
  does not record which tools ran, so the cause took a state dump to find.
- Same pattern elsewhere in the project: `route_advice` / `voyage_watch` = "code computes, the model writes"
  (ADR-057 / ADR-058). The pack's KPI and audit steps are already deterministic nodes (`kpi`, `audit`); only the
  external context is still left to the model.

## 1. Owner decisions (to ask once, as clickable choices, recommendation first)

| # | Question | Recommended | Alternatives |
|---|---|---|---|
| E1 | What the code fetches every week | **Suez transits (the week + the 4 weeks before) + the week's news** | + one fixed tariff-rule search (`search_documents`) every week |
| E2 | The two tools in the Insight agent's own list (pack only) | **Removed** (the data is already in its input; no second Tavily credit for the same week) | Kept for drill-downs (another window or query) |
| E3 | The news query | **Fixed by code** ("Suez Canal Red Sea shipping", the week's dates, 3 results) | Written by the model from the week's findings (one more call, varies by run) |
| E4 | Acceptance (ADR-052) | **Golden weeks twice (candidate) vs the c5b baseline; Q&A not re-run** (the Q&A agent and `STAGE1_TOOLS` are not touched — ADR-052 sixth-use precedent D-RR-1) | Full ADR-052 (golden weeks + Q&A, EN + AR, twice) / fake checks + one live pack only |
| E5 | Commit | **One commit when this plan closes**, separate from C4 | Folded into C4 (then this plan waits) |

**Owner's answers (2026-11-07):** E1 Suez + news (recommended); **E2 kept for drill-downs** (over the recommended
"removed"); E3 fixed by code (recommended); E4 + E5 golden weeks twice + a separate commit (recommended).

## 2. Design (PROPOSED)

### 2a. A deterministic node `external_context`
- Placed `audit → external_context → insight_llm`. It calls, as the run's user (RBAC `PUBLIC_EXTERNAL` as today):
  - `external.suez_transits(user, start = week_start − 28 days, end = week_end)` → evidence `context.suez`;
  - `external.web_search(user, query = NEWS_QUERY, start_date = week_start, end_date = week_end, max_results = 3)`
    → evidence `context.news` (E3).
- Every outcome is stored as it is (`ok` / `no_data` / `context_unavailable` + its note), so the reason for a missing
  slide 9 is in the state. A tool exception is caught into `context_unavailable` (the pack never stops for context).
- The existing `ExternalCache` keeps settled windows (one Tavily credit per week, re-runs and resumes read the
  cache); a revise does not re-fetch (the node runs once, before the Insight).
- Dataset `test` (golden weeks): the same public calls (the data is public, not NileGate's), cached after the first
  run.

### 2b. What the Insight agent sees
- The digest adds `context.suez` (`date | n_total`, the mean) and `context.news` (`title | published_date | url |
  snippet | trust`): news rows keep their `trust: web_content` label and are screened as today (ADR-042 note), so the
  `untrusted-content` skill still applies.
- `INSIGHT_TASK`: "External context for the week is already fetched below (context.suez, context.news); do not fetch
  the same window again — call suez_transits / web_search only for a drill-down (another window or query), and
  search_documents for a tariff rule."
- E2 (owner: kept): the Insight's tools stay `STAGE1_TOOLS`, unchanged (the finance Q&A agent shares them). A repeat
  of the node's own call (same normalized query and window) is a cache hit in `ExternalCache`: no second Tavily
  credit; a different window or query costs one, at most `MAX_TOOL_ROUNDS` as today.

### 2c. Slide 9 and the record
- `validator.SLIDE_EVIDENCE[9]` = `("context.*", "insight.*")` (the tariff rule still comes from an `insight.*` call);
  ADR-051 amendment.
- `render.suez()` already finds the transits by tool name in all the evidence: the chart works unchanged.
- `run.json` gains `external_context: {suez: <status>, news: <status>, notes}` — the next "unavailable" has its reason
  in the published record.
- A missing context stays what it is today (slide 9 "External context unavailable" + caveat "missing context"), now
  with the stated reason.

## 3. Tests
- `Weekly_pack_check.py` (fake models, 0 calls): a new phase — the context is fetched when the scripted Insight calls
  no tool; an unavailable source → `context_unavailable` + its reason in the state and in `run.json`; a scripted
  drill-down with the node's own args is a cache hit (no second fetch), one with another window is a new call (E2);
  a revise does not fetch again; the fake scripts that called those two tools still pass.
- `Deck_check.py`: slide 9 bullets citing `context.*` pass; a slide-3 bullet citing `context.news` is refused.
- `Injection_eval.py` Phases 1–3: the news now reaches the Insight through the digest instead of a ToolMessage — the
  frozen set's web rows must still be screened and labelled (gates unchanged).
- Lint ratchet 0 / 0, pyright, `Scheduler_check.py` 6 / 6, the OpenAPI snapshot (unchanged).
- Acceptance per E4; then one live pack (W15, Monday 2026-11-09, or run early) shows slide 9 with Suez + news lines.

## 4. Phases
| Phase | What | Done when |
|---|---|---|
| A | The node, evidence ids, digest, prompt, pack tool list, `SLIDE_EVIDENCE[9]`, `run.json` field | code + lint clean |
| B | Checks (§3, fake) | all pass |
| C | Acceptance (E4) | ADR-052 gates held, no primary falls > 0.03 |
| D | Docs: ADR-050 amendment 3, ADR-051 amendment 6, `ARCHITECTURE.md` (pack row), skills `weekly-variance-analysis` + `deck-style-guide` (slide 9 line) — **skill edits reviewed by the owner** | the owner's yes on the skills |
| E | One live pack | slide 9 shows the week's Suez transits and news without the model calling them |

## 5. Done when
- Every weekly pack has the week's external context fetched by code, or a stated reason why not, whatever the model
  chooses; slide 9 is no longer a model's coin toss.
- ADR-052 gates held (E4); the owner reviewed the two skill edits; one live pack shows it.

## 6. Risks / uncertain
- Tavily free credits (1,000 / month per its free plan, uncertain — not checked in the account): one credit per pack
  week + one per golden week on the first eval run, then the cache.
- PortWatch was unavailable during both W13 runs (status `context_unavailable`): code fetching does not fix an outage,
  it only records it.
- The new input and prompt line change the Insight's notes (wording, which context it cites): that is what the
  acceptance run (C) measures. With the tools kept (E2) the model may still re-fetch with another window — counted
  in the eval report (calls per pack).

## Progress / deviations
- 2026-11-07 — written PROPOSED after the W14 live check (Pack_approver_additions_plan, Progress 2026-11-07).
- 2026-11-07 — E1–E5 asked as clickable choices: all as recommended except **E2 = tools kept for drill-downs**;
  §2b / §3 / §6 updated. Waiting for the owner's approval of the plan.
- 2026-11-08 — resumed as PROPOSED (the approver-request and approver-additions plans archived 2026-11-07); waiting for
  the owner's approval.
- 2026-11-08 — **APPROVED** (owner: "موافق، ابدأ"). **Phase A done:** `weekly_pack.py` — node `external_context`
  (`audit → external_context → insight_llm`): `context_evidence(user, evidence)` fetches `context.suez`
  (`suez_transits`, the week − 4 weeks … the week end) and `context.news` (`web_search`, NEWS_QUERY "Suez Canal Red Sea
  shipping", the week's dates, 3 results), each outcome kept as returned, an exception → `context_unavailable` with
  its reason; digest fields for both (news with `trust`); the Insight prompt line (already fetched, do not fetch the
  same window again; tools for a drill-down or a tariff rule); `run.json` `external_context` (status + note per id).
  `models.EVIDENCE_ID` accepts `context.*`; `validator.SLIDE_EVIDENCE` slide 9 = `context.*` + `insight.*`, slide 2
  gains `context.*`. On W14 the real fetch returned 35 transit days + 2 news items.
  - **D-EC-1:** `build_graph(context_fetch=…)`: the default for real models is `context_evidence`; for `FakeRoles`
    it is `no_context` (no network, a stated note) — otherwise every check run (52 weeks in `Weekly_pack_check`)
    would spend Tavily credits.
- 2026-11-08 — **Phase B done:** `pipelines/scripts/agents/External_context_check.py` (**D-EC-2:** its own short script
  instead of a phase of the 12-minute `Weekly_pack_check`) Phases 1–3 passed: fetched with an Insight that calls no
  tool, in the Insight's and the Writer's input (news labelled web_content), once per pack (none on a revise); an
  outage → the reason in the state and the published `run.json`; context.* ids and slides 2 / 9 (not 3).
  No-regression: `Weekly_pack_check` 9 / 10 (paths and evidence keys gained `external_context` / `context.*`;
  Phase 5 = real models, on request), `Deck_check` 8 / 8, `Scheduler_check` 6 / 6, `Approver_request_check` (its
  D-AR-11 expectation updated: an approve with a steer is read as a change), `Injection_eval` 1–3; ruff / pyright /
  ratchet clean. The plan's "cache hit on a drill-down with the node's args" is existing `ExternalCache` behaviour,
  not re-tested here.
  - **Phase C started then stopped (D-EC-3):** the golden-week run was started before the two skill edits of Phase D;
    the skills are part of the Insight / Writer prompts, so it was stopped within minutes and the skills were edited
    first (`weekly-variance-analysis` step 7: context already fetched, cite `context.suez` / `context.news`, tools for
    a drill-down; `deck-style-guide` slide 9's evidence column: `context.*` + Insight results). **Waiting:** the
    owner's review of the two skill lines, then Phase C on the final prompts.
- 2026-11-08 — the two skill lines reviewed and approved by the owner ("تمام، شغّل التقييم"); Phase C started on the
  final prompts.
- 2026-11-08 — **Phase C, candidate ec1** (`stage1_eval_2026-11-08_ec1.json`, golden weeks × 2, scope packs): every
  gate held in both runs (deck numbers 100 %, planted 6 / 6, false alarms 0, claims 100 %, traceability 100 %);
  narrative recall **0.931 = c5b's 0.931** (a tie). **But slide 9 was not yet right:** 21 / 22 decks carried both the
  real context (the Suez chart, news lines citing `context.news`) **and** the code line "External context unavailable
  for this week". Cause found: the Writer summarised the 35 daily transit rows in its own words ("ranged between 28
  and 45 calls per day") — the numbers were right (W16: min 28 on 04-15, max 45 on 04-18) but bound to no field the
  Validator could check (no row named; and `slots.SLOT_RE` did not accept `context.` ids, so the Writer could not use
  a slot) → V2 refused, the rewrites did not fix it, the c4 fallback put `sample.py`'s line in its place (each pack
  = 5 calls: 2 rewrites).
  - **D-EC-4:** `slots.SLOT_RE` and the patch's evidence-id scan accept `context.`; `context_evidence` adds code's week
    summary to `context.suez` (`transit_week`: `week_mean_transits`, `week_min_transits` / `_date`,
    `week_max_transits` / `_date`, `prev4_mean_transits` — result-level fields, so a slot or a literal binds), shown as
    one line in the digest. The cached W16 draft re-validated: its slide-9 lines now pass; the one problem left is the
    Writer's slide-9 **title** "30 to 45" (a real error: the minimum is 28), refused as it should be.
    `External_context_check` (+ the summary and a context slot) and `Deck_check` 8 / 8 passed.
  - **Candidate ec2** (the same plan + D-EC-4) running: golden weeks × 2. Quota: the Gemini day showed 206 / 500
    before it.
- 2026-11-09 — **Phase C done: ec2 kept** (recorded by the traffic-billing link plan's session; the owner chose there
  to close this plan: "قفّل خطة السياق وكمّل الربط"). `Data/processed/agents/eval/stage1_eval_2026-11-08_ec2.json`
  (finished 2026-11-08 15:39): every gate held in **both** runs (packs 11 / 11, deck numbers 100 %, planted 6 / 6,
  false alarms 0, claims 100 %, traceability 100 %). Narrative recall 0.8966 / 1.0, **mean 0.9483 vs c5b's 0.931**
  (+0.017: no primary fell, ADR-052). Writer rewrites 22 per run (as ec1). Run 1 had 27 failed calls and 26
  fallbacks (Gemini 503 "high demand", OpenRouter timeouts), all recovered; run 2 had 1 failed call. The Q&A was not
  re-run (E4).
- 2026-11-09 — **Phase E, first try: the scheduled W16 pack** (Task Scheduler, Monday 10:30, `run_as` 6,
  `weekly_pack:live:2025-W16:1`) ended `output_invalid`. The code-fetched context reached the Insight (its notes cite
  the week's Suez transits, mean 35.6, min 28 on 04-15, max 45 on 04-18, and a Newsweek item of 2025-04-14). But
  the Writer (gemini-3.5-flash-lite) answered twice with a DeckDraft whose evidence ids carried a row
  (`kpi.category[Liquefied Natural Gas …]`), which `models.EVIDENCE_ID` refuses, so there was no deck (`_stop`, owner
  rule 2026-10-19). This is model variance, not this plan's code: the 22 ec2 packs never did it. Re-run as a new
  attempt (`Weekly_pack.py run --week 16 --as 6`).
  - **W16:2 failed the same way:** the LLM cache replays the same reply (by design), so a re-run cannot fix it.
  - **D-EC-5:** `models.norm_ids` drops a trailing `[row]` from an evidence id before the `EVIDENCE_ID` check
    (`Cited`, the deck bullet, `DeckPatch`, the Q&A answer); any other malformed id is still refused. A unit check
    passed; `Deck_check` 8 / 8, `External_context_check` and the lint ratchet are clean.
  - **W16:3 reached `awaiting_approval`.** Slide 9 had two news lines (`context.news`) **and** the line "External
    context unavailable for this week": the Writer's transit line failed its rewrites, and the c4 fallback put
    `sample.py`'s fixed line in its place.
  - **D-EC-6:** `sample.py` now writes slide 9 from code's week summary when `context.suez` is ok (the mean and the
    previous four weeks as result slots; the quietest / busiest day from their own rows, as V7 requires). On W16's
    real evidence the whole code draft passes the Validator. ADR-051 amendment 7 (3) and (4).
  - W16:4 run with both fixes; `Weekly_pack_check.py` (fake models) re-run.
