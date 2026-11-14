# Plan — the approver changes the weekly pack before it is published; a "smart" finance view

**Status: IMPLEMENTED (2026-11-07)** — approved 2026-11-06 (owner: "موافق"); Phases A–H implemented 2026-11-06.

## Implementation record (2026-11-07)
- **Done when — met.** `Weekly_pack_check.py`, `Deck_check.py`, `Api_check.py` passed (Phase 5 of the pack check =
  real models, run only on request); `Views_eval.py` exact 0.9667, leakage 0 (D6); the Power BI field parameters,
  the compare week and the bookmarks on the page Smart View, = SQL on weeks 5 / 23 / 49 (Phase G, saved 2026-11-06);
  the Phase H ADRs (ADR-048 am. 2, ADR-050 am. 2, ADR-051 am. 5, ADR-066); the live check on a real pack — **W14**,
  run early at the owner's request ("طب ما تشغل pack دلوقتي", then "جرّب الخطوات", 2026-11-07), the steps run by
  Claude as the Finance manager: an added bullet + a trend variant (Validator passed), one revise with a steer (the
  re-draft explained the overdue change; D2 dropped the addition and the variant as decided), approve → published
  `reports/2025-W14/` (`approval.json` holds the three decisions).
- **Follow-ups found on W14:** slide 9 was "External context unavailable" because the Insight model called no
  context tool that week (Tavily / PortWatch were up) → `docs/plans/Pack_external_context_plan.md` (written
  2026-11-07, DEFERRED behind the approver-request plan); the manager could not yet say his change in words →
  the approver-request plan (closed 2026-11-07, ADR-067, `docs/archive/2026-11-07_Approver_request_plan.md`).
- **Commit:** C4 (one commit of this plan) — the owner's.

Original status line: **Status: APPROVED (2026-11-06, owner: "موافق") — Phases A–H implemented 2026-11-06; open: the owner's three steps
(Progress, last entry), then the implementation record and the archive** — written 2026-11-05, widened the same day;
the owner's request of 2026-11-05 ("الـ manager ممكن يضيف
تعليق ع الـ report قبل ما يتنشر أو يعدّل ع حاجة مش عاجباه أو حاجة عايز يضيفها"), his answers B1–B3, then his follow-up the
same day: the approver may also change **the analysis** and **the charts**, and a **"smart" Power BI view** that adapts
when asked (answers C1–C4 below). No code before the owner approves this plan. Touches ADR-048 (Power BI), ADR-050 (the
approval interrupt), ADR-051 (the deck, the Validator), ADR-052 (acceptance rule), ADR-060 (frontend), ADR-064 (API).

## 0. What exists and what is missing

| Wish | Today (EXISTING) | Missing |
|---|---|---|
| comment before publishing | `ApprovalDecision.comment` — kept in the approval log, `approval.json`, `Weekly_pack.py show`, `GET /api/v1/packs/{thread}` | — (the owner keeps it out of the deck, answer B1) |
| change a bullet's text | `decision: edit` with `edits: [{bullet, text}]` → re-validated (V1–V9, V8 read-back) → waits again (ADR-050 (3)); CLI `Weekly_pack.py resume --decision edit --edits`, API `POST /packs/{thread}/decision` | — |
| add something new | — | **a new bullet on a slide the approver picks**, through the same Validator (§2a) |
| change the analysis | the Insight notes (`state["insight"]`: 5 summary points, ≤ 3 drivers, context, caveats) feed the Writer as the `[insight notes]` block; the approver never sees them | **structured edits of the notes** and **a free-text steer that re-runs the Insight agent**, both followed by a Writer re-draft (§2b, answer C1) |
| change a chart | code draws `chart:trend` (s4), `chart:variance` (s5), `chart:aging` / `chart:overdue_flow` (s6), `chart:suez` (s9) from the evidence; fixed series, period and breakdown | **a code catalogue of chart variants** recorded in the draft, drawn by code, read back by V8 (§2c, answer C2) |
| a view that adapts when asked | Power BI Desktop, 5 + 1 pages, one synced week slicer (ADR-048) | **field parameters, a compare-week table and bookmarks** in the PBIP, and **`POST /api/v1/views`** — a question in words → a chart from the same catalogue, numbers fetched by code under the asker's RBAC (§2d, answer C3) |

## 1. Owner decisions (asked 2026-11-05, as clickable choices)

| # | Decision | Answer |
|---|---|---|
| B1 | Where the approver's comment shows | **Not in the deck** — it stays in the approval log / `approval.json` (as today) |
| B2 | How new text is added | **A new bullet that passes the Validator** (recommended): the approver picks the slide; any number in it must bind to that slide's evidence (as an edit's literals do, ADR-051), else it is refused with the reason; marked as the approver's addition |
| B3 | What happens after an addition | **Re-validated and waits again** (recommended): Validator + V8, a new preview, a second click to approve |
| C1 | How the approver changes the analysis | **Both** (the owner widened the recommendation): structured edits of the Insight notes → one Writer re-draft, **and** a free-text steer that re-runs the Insight agent (tools + notes) → the Writer; both re-validated, both wait again |
| C2 | How far a chart change may go | **A fixed code catalogue + a code fetch for 26 weeks** (recommended): per chart, series / period / breakdown variants of fields the evidence already has; 26 weeks = code calls `finance_kpi(trend, week − 13)` with the run's identity; every value a view field, read back by V8 |
| C3 | The "smart" view | **Both** (recommended): Power BI Desktop field parameters + bookmarks (choice by click), **and** `POST /api/v1/views` (choice in words: one small LLM call picks from the same catalogue, code fetches the numbers under the asker's RBAC; the web UI draws it later, ADR-060) |
| C4 | Commits | **One commit when the whole plan closes** (recommended); the owner commits (no AI attribution) |

**Detail decisions D1–D6 (asked 2026-11-06 as clickable choices, owner's answers):**

| # | Decision | Answer |
|---|---|---|
| D1 | Mixing kinds in one decision | **One kind per decision** (recommended): `approve` / `edit` (text edits, additions, chart changes) / `revise` (analysis edits and / or a steer, chart changes allowed) / `reject`; `revise` with text edits or additions → refused with the reason (a re-draft replaces the Writer's text, so an edit to it would be lost silently) |
| D2 | The approver's earlier changes after a `revise` | **Nothing is carried — the re-draft starts clean** (the owner's choice over the recommended "carry additions, list edits"): the new draft holds only the Writer's text on the revised notes, default charts plus the chart changes of the `revise` decision itself; the approver re-adds what he still wants. The interrupt payload says `redrafted: true` and the approval log keeps every earlier change (nothing is lost from the record, only from the deck). Simpler code: no carry-over or re-binding of old additions |
| D3 | Caps per pack | **Medium** (recommended): ≤ 2 `revise` per pack (quota, ADR-045), steer ≤ 300 chars, ≤ 10 analysis edits / decision, ≤ 3 chart changes / decision, ≤ 2 additions / slide, ≤ 300 chars / addition — flash-lite's 500 free requests / day are shared with the scheduled runs |
| D4 | G5 edit rate | **One rate + counts per kind** (recommended): `edit_rate` counts a pack with **any** approver change (edited or revised); the report adds counts per kind (text edits, additions, analysis edits, steers, chart changes) |
| D5 | A view question that names no week | **Ask back** (recommended, ADR-065 style) instead of guessing; the model sees **only the question and the catalogue** (never data) |
| D6 | The views gate | **30 questions, ≥ 0.90** (recommended): 15 EN + 15 Egyptian AR, frozen before the first real run; the chosen variant exactly right ≥ 0.90, RBAC leakage 0 (a rule fixed in advance, as ADR-052) |

## 2. Design (PROPOSED)

### 2a. Additions (owner B2 / B3, unchanged from the first version)

1. `ApprovalDecision.additions: list[Addition]` with `Addition(slide, text)`; `decision: "edit"` carries edits and / or
   additions and / or chart changes (at least one).
2. **Where an addition may go** (fixed in code, read from the deck's shape rules — Phase A lists them): only slides
   whose bullets are free text (not slide 1's title block, not the code-drawn tables / charts / tiles, not the
   sources slide); appended after the Writer's bullets, so V4 and V8 hold. A refused placement → `refused` with the
   reason, the pack keeps waiting.
3. **The bullet:** `{slide, text, evidence_ids = the slide's evidence ids, origin: "approver"}` — numbers are literals
   bound by search (V2's human-edit path), wording through V9; an unbound number → `validation_failed` problems shown
   to the approver. Rendered with a small mark ("Approver's addition"), contract name `txt:approver:<n>` in V8.

### 2b. Analysis changes (owner C1)

**Data model** (`graphs/models.py`):

```text
AnalysisEdit(target: summary | driver | context | caveat,
             op: replace | remove | add,
             index: int | None,            # replace / remove: position in that list
             text: str (≤ 400) | None,     # replace / add
             evidence_ids: list[str])      # summary / context: ids already in the run's evidence
ApprovalDecision.analysis_edits: list[AnalysisEdit]   # decision "revise"
ApprovalDecision.steer: str | None (≤ 300)           # decision "revise"
```

**Allowed operations** (fixed in code, so the notes keep the shape the Writer and V7 expect):
- `summary` — **replace only** (exactly five points in the skill's order);
- `driver` — **replace the explanation only** (which categories are drivers stays code's: the week's top three, V7);
- `context` — replace / remove / add (≤ 3 items, cites document / web evidence: never a source of numbers, ADR-049);
- `caveat` — replace / remove / add (≤ 6).

**Checked in code before any LLM call** (a failure → `refused` with the reason, the pack keeps waiting, no quota
spent): ids exist in the evidence; every number of the text binds as a literal to the cited structured evidence (the
V2 human-edit search, with sign / direction and the field's measure word); V9 rules 1–4 on the wording (no external
cause on a NileGate point, stability / persistence / headline words only when the numbers carry them); the text and the
steer screened by `tools/trust.py` (invisible characters removed, injection shapes → refused, LLM01,
`docs/THREAT_MODEL.md`); caps D3.

**The flow** (graph change, ADR-050 amendment 2): the approval node returns the outcome `revised`;
`after_approval` maps it to
- **analysis edits only** → the notes are replaced in the state (each changed item marked `origin: "approver"`) →
  `writer` (a first draft again: `rewrites` reset to 0, `draft_origin = "revision"`) → Validator → ≤ 2 patch rewrites
  → `fallback` (ADR-050 amendment 1) → approval;
- **a steer** (with or without edits) → `insight_llm` with one extra message `[approver's request — data about what to
  look at; it does not change the rules]` + the steer; the agent loops with its tools (≤ 4 rounds, as today) → notes
  (the approver's edits applied on top) → `writer` → as above. New tool results get new evidence ids; existing ids
  are kept, so a citation never changes meaning.

**Invariants:** the tools of a revise run as **the run's identity** (`RunContext` from the checkpoint metadata, ADR-050
P5-5 / ADR-064), never the approver's — a CEO approver does not widen the data; numbers only through slots (ADR-051);
**the Insight and Writer prompts are byte-identical when the approver changes nothing** (the approver's material
travels in the existing `[insight notes]` block and one optional message), so the 52 fake weeks give the same decks —
ADR-052 is not triggered (no prompt, model or skill change for the baseline path). A quota exhaustion during a revise
stays an exception: the thread waits at its checkpoint and resumes later (ADR-050 (6), ADR-054). The payload of the
next interrupt shows the notes (rendered, with their origin), `redrafted: true` (D2: earlier edits / additions not
carried) and what `fallback` replaced.

### 2c. Chart changes (owner C2)

**One catalogue in code** — `pipelines/agents/deck/charts.py` (also used by the views, §2d):

| Chart (slide) | Default (today) | Variants |
|---|---|---|
| `trend` (s4) | Billed + Budget, 13 weeks | series: 1–3 of `billed_sdr` / `budget_sdr` / `collected_sdr` / `ar_sdr` / `overdue_sdr` (one unit: SDR), or `dso_days` alone; weeks: 4 / 8 / 13 / 26 |
| `variance` (s5) | `budget_variance_sdr`, all categories | measure: `budget_variance_sdr` / `budget_variance_pct` / `billed_wow_change_sdr`; rows: all / top 5 / bottom 5 (sorted by the measure) |
| `aging`, `overdue_flow` (s6), `suez` (s9) | — | **fixed** (no variant of real value; Phase A confirms) |

**Data model:** `ChartChoice(chart, series | None, weeks | None, measure | None, rows | None)`;
`ApprovalDecision.charts: list[ChartChoice]`; the draft gains `DeckDraft.charts: dict[str, ChartChoice]` (empty =
today's charts), so `deck_draft.json` records what was drawn and the publisher redraws the same thing.

**Rules (code, at the approval node → `refused` with the reason):** the chart and every option in the catalogue; one
unit per chart (no SDR next to days); 26 weeks only when `week − 13 ≥ 1` (then code calls `finance_kpi(trend,
week − 13)` with the run's `RunContext` and stores it as `kpi.trend_prev`, allowed on slide 4); a 4 / 8-week window is
a slice of `kpi.trend`. **Drawing and checking:** `render.build_spec` reads `draft.charts`; V8 compares the chart's
categories, series names and values with the evidence fields as it does today (no new V-rule). The Writer's comments
are not rewritten by a chart change (the approver sees the new preview before approving; he may edit a comment in the
same decision).

### 2d. The "smart" view (owner C3)

**The honest free options** (Power BI stays Desktop on DirectQuery over `finance` through `ports_bi`, ADR-048):

| Option | Adapts how | Cost / limit | In this plan |
|---|---|---|---|
| Field parameters (series / breakdown chosen by a slicer) | by click | free; a calculated table in a DirectQuery model — **uncertain** on Desktop 2.158 with PostgreSQL: Phase G1 tests it first | **yes** (fallback: bookmarks + buttons) |
| A compare-week table (a second DirectQuery table on `finance.dim_week`, no relationship) + `TREATAS` measures | by click: week A vs week B | free; a fourth DAX pattern (still reads SQL values, no KPI logic in DAX) — ADR-048 amendment 2 | **yes** |
| Bookmarks + buttons ("This week" / "13 weeks" / "Compare") | by click | free, static states | **yes** |
| The model edits the PBIP through the Modeling MCP | at development time only | needs Desktop open and the owner; not a reader feature | used to **build** the above, not at run time |
| Q&A visual (questions in words inside Power BI) | in words | **uncertain** support on PostgreSQL DirectQuery; Microsoft is moving this to Copilot (paid capacity) | **no** (not relied on) |
| Embedding / Power BI Service / Copilot | in words, shared | **paid** licence or capacity | **no** — the upgrade path (ADR-048 D5) |
| Publish to web | — | **public** to anyone with the link: company data | **rejected** |
| `POST /api/v1/views` + the web UI (ADR-060) | **in words** | free (one small `tools`-role call, shared quota) | **yes** — the API now, the drawing in the frontend plan |

**The API view:**
- `POST /api/v1/views` with **either** `{"choice": ViewChoice}` (code only → 200 with the `ViewSpec`) **or**
  `{"question": "…"}` (≤ 300 chars → 202 + run id; SSE `done` carries the `ViewSpec`, ADR-064 (3)).
- `ViewChoice` = the §2c catalogue widened for readers: `trend`, `category` (+ an optional `compare_week` → two
  series), `aging` (+ `compare_week`), `customers` (top 10 by `share_13w_pct` / `ar_sdr` / `overdue_sdr`) + `week`.
- The question goes to **one structured call** (`tools` role: flash-lite + gpt-oss-20b fallback, ADR-045) whose output
  schema is `ViewChoice` with Literal enums — the model sees the question and the catalogue only, **never data** (D5);
  no week in the question → `ask_back`.
- Code fetches through `finance_kpi` with **the asker's** `RunContext` (RBAC checked in the tool, ADR-049); a
  `not_permitted` result → the problem+json body, no values; `ViewSpec` = `{choice, categories, series: [(name,
  values)], unit, source}` — every value a view field (= Power BI = the pack); the caption is written by code.
- `GET /api/v1/charts/catalogue` (the same catalogue for the pack's approval screen and the view).
- CLI for now: `pipelines/scripts/agents/View.py --as <id> (--ask "…" | --choice <json>) [--pptx out.pptx]` — prints
  the spec; `--pptx` draws a one-slide PPTX with the deck's own chart code and reads it back (V8), so the view can be
  seen before the web UI exists.

## 3. Interfaces (API + CLI)

| Where | Change |
|---|---|
| `POST /api/v1/packs/{thread}/decision` | body: `decision ∈ approve / edit / revise / reject`; `edits`, `additions`, `charts`, `analysis_edits`, `steer`, `comment`; schema-level 422 for a wrong mix (D1), an empty `edit` / `revise`, a chart or option not in the catalogue, over-long text; the rest (evidence binding, slide rules, caps per pack) → the run's `refused` with the reason |
| `GET /api/v1/packs/{thread}` | adds `insight` (notes rendered, with origin), `charts` (current choices), `redrafted`, `degraded` |
| `GET /api/v1/packs/report` | per-kind counts (D4) |
| `POST /api/v1/views`, `GET /api/v1/charts/catalogue` | new (§2d) |
| OpenAPI snapshot | regenerated (`tools/openapi_snapshot.py`, CI) |
| `Weekly_pack.py resume` | `--decision revise`; `--add "4: <text>"` (repeatable), `--chart '<json>'` (repeatable), `--analysis <file.json>`, `--steer "<text>"`; `show` prints the notes with indexes and the current charts |
| `Weekly_pack.py report` | per-kind counts (D4) |
| `View.py` | new (§2d) |

## 4. Tests

- **`Weekly_pack_check.py`** (fake roles, weeks 5 / 10 / 23 / 49): additions (as in the first version); **charts** —
  each catalogue variant → preview, V8 passes, approve → `deck.pptx` + `deck_draft.json.charts`; 26 weeks on W23 →
  `kpi.trend_prev` fetched **as the run's user**; 26 weeks on W10 → refused; mixed units / unknown option → refused;
  **analysis** — a summary replace with an unbound number → refused **with 0 LLM calls**; a valid replace → one Writer
  call, validated, waits; a caveat removed / added; a driver's explanation replaced; a category swapped into the
  drivers → refused; **steer** — Insight re-runs (fake), new evidence ids, old ids unchanged; an injection-shaped steer
  → refused; a third `revise` → refused; `revise` + edits → refused (D1); after a `revise` the new draft holds no
  earlier addition / edit and the default charts + that decision's chart changes, `redrafted: true`, the approval log
  still lists the earlier changes (D2); a CEO approver → the tools still run as the configured Finance manager; a quota exception inside the
  re-draft → the thread waits, a later resume finishes; the approval log and the G5 counts per kind.
- **`Deck_check.py`**: every chart variant on weeks 5 / 10 / 23 / 49 → 0 V8 false alarms; planted chart faults (a
  series swapped, a value off, a window shifted by one week, the wrong measure under a measure's name) all caught by
  V8; the 52 clean decks with default charts **byte-identical** to before (SHA-256) — proves no regression; additions
  read back (first version).
- **`Api_check.py` Phase 7** (packs): an `edit` with charts → 202 → `approval_needed` → approve → the deck holds it; a
  `revise` → the SSE shows `insight_*` / `writer` / `validator` nodes → `approval_needed`; 422 for each wrong mix; a
  non-approver refused (as today). **New Phase 11** (views): an explicit choice = `finance_kpi` values; a question
  (fake roles) → the right `ViewSpec`; an employee without finance access → not permitted, **leakage 0**; the quota
  counted once per question.
- **`Views_eval.py`** (new, real model once): the frozen 30-question set (D6) → exact-variant rate ≥ 0.90, ask-back
  on the no-week items, leakage 0; results `Data/processed/agents/eval/views_eval_<date>.json`.
- **Power BI** (Phase G): every new measure / field-parameter state = SQL for weeks 5 / 23 / 49 (Modeling MCP DAX
  query vs `finance.*`), the compare-week pair W22 vs W23; `db/check_finance_bi_user.py` unchanged (11 / 11).
- **No regression:** `Stage1_eval.py` fake (Phase 3c), `Scheduler_check.py`, `Injection_eval.py` (frozen set
  unchanged; the steer's injection cases live in `Weekly_pack_check.py`), the lint ratchet, pyright, the OpenAPI
  snapshot in CI.

## 5. Phases

| Phase | Content |
|---|---|
| A | Read-only study: the free-text slides (V4, `render.py`), which charts have useful variants, how readback compares charts; then `models.py` (`Addition`, `AnalysisEdit`, `ChartChoice`, `ViewChoice`, `ViewSpec`, `ApprovalDecision` widened) and `deck/charts.py` (the catalogue) |
| B | Additions: render + `txt:approver:<n>` + the mark; Validator on additions (V2 literals, V9) |
| C | Charts in the pack: `build_spec` reads `draft.charts`, the approval node's chart rules, the 26-week fetch, V8 cases |
| D | Analysis: `revise` outcome and edges, notes validation before any LLM call, the steer message, the clean re-draft (D2), caps (D3), the interrupt payload |
| E | CLI + API for the pack, OpenAPI snapshot, G5 counts per kind |
| F | Views: `POST /views`, catalogue endpoint, the structured call, `View.py` (+ one-slide PPTX), the frozen golden set + `Views_eval.py` |
| G | Power BI (on screen with the owner, ADR-048 (7)): G1 a field-parameter spike in the DirectQuery model (fallback: bookmarks + buttons); G2 series / breakdown parameters on Revenue; G3 the compare-week table + `TREATAS` measures; G4 bookmarks; values checked against SQL |
| H | Checks green, ADRs (ADR-050 amendment 2, ADR-051 amendment 5, ADR-048 amendment 2, **ADR-066** the shared chart catalogue + the views endpoint, ADR-064 note), `ARCHITECTURE.md`, `docs/THREAT_MODEL.md` (the steer and the view question as LLM01 surfaces), `docs/ROADMAP.md`, plan archived; the owner commits once (C4) |

## 6. Done when

- `Weekly_pack_check.py`, `Deck_check.py`, `Api_check.py` (Phase 7 + the new Phase 11) all pass; the no-regression
  list in §4 passes; the 52 default decks are byte-identical to before.
- `Views_eval.py` meets D6 (≥ 0.90 exact variant, leakage 0).
- The Power BI pages hold the field parameters (or their bookmark fallback, recorded), the compare-week view and the
  bookmarks, every value equal to SQL for weeks 5 / 23 / 49.
- The ADRs of Phase H written; the skill `deck-style-guide` unchanged (the Writer's prompt for the baseline path is
  unchanged).
- The owner, on a live pack (Monday 2026-11-09 or later): adds a bullet, changes one chart and revises the analysis
  once, then approves.

## Progress / deviations

- 2026-11-05 — written (PROPOSED) after the FastAPI plan was archived; owner decisions B1–B3 recorded.
- 2026-11-05 — widened (still PROPOSED) for the owner's follow-up: analysis and chart changes, the smart view; owner
  decisions C1–C4 recorded (C1 "both", the others as recommended); defaults D1–D6 proposed.
- 2026-11-06 — D1–D6 asked as clickable choices: all as recommended except **D2 = nothing carried after a `revise`**
  (a clean re-draft).
- 2026-11-06 — **APPROVED** by the owner; Phase A started. The owner also asked for the frontend plan in parallel
  (its own session, plan only); it could not be started from a Remote Control turn — to be started from the desktop
  app.
- 2026-11-06 — **Phase A done** (handoff). Study findings → deviations from §2:
  - **D-A1 — nothing new on `DeckDraft` or `Bullet`:** they are the Writer's structured-output schema, so a new field
    would change its prompt (and trigger ADR-052). Chart choices live in the graph state (`charts`, passed to
    `render` / `readback` beside the draft, written to `run.json` / a `charts` key only when not default); an
    addition is a draft bullet dict with an extra key `origin: "approver"` outside the schema (the dict is the state;
    the Validator's model parse ignores the key, the renderer reads it).
  - **D-A2 — V8 compares the file with the spec, not with the evidence:** `readback._compare` checks a chart against
    `build_spec`'s element, which `render` builds from the evidence. A variant drawing the wrong field would pass V8.
    Phase C adds an independent check: each drawn series = its catalogue field read straight from the evidence.
  - **D-A3 — window rule:** the data hold 2025 only, so an N-week trend needs report week ≥ N (not `week − 13 ≥ 1`):
    26 weeks from W26. The default 13-week trend keeps today's "weeks 1–w".
  - **D-A4 — where additions fit:** free-text slides are 3–8 (comments, V4 ≤ 3) and 9 (context ≥ 1); slide 2's five
    bullets have a fixed layout, slides 1 / 10 are code's. `comments()` shrinks the type to 10 pt to fit; slide 5's
    comment column is 3.5 in wide — Phase B measures whether 3 + 2 comments fit on each slide and lowers the cap per
    slide where they do not. V4 counts the Writer's comments and the approver's apart.
  - Code: `pipelines/agents/deck/charts.py` (the catalogue: pack charts `trend` / `variance`, fixed `aging` /
    `overdue_flow` / `suez`, view kinds, `problems` / `view_problems` / `resolve` / `is_default` /
    `needs_previous_trend` / `catalogue`); `graphs/models.py`: `Addition`, `ChartChoice`, `AnalysisEdit`
    (`ANALYSIS_OPS`), `ApprovalDecision` (`approve` / `edit` / `revise` / `reject`, D1 shape rules, D3 caps),
    `ViewChoice` (validated by `charts.view_problems`), `ViewSeries`, `ViewSpec`; `weekly_pack.approval` refuses
    additions / chart changes / `revise` with a clear reason until Phases B–D enable them. The API's body still
    accepts `approve` / `edit` / `reject` only (Phase E).
  - Checks: model + catalogue cases by hand (16 cases as expected, `render.AGING` = `charts.AGING_BUCKETS`); lint
    ratchet 0 / 0; `Weekly_pack_check.py` 6 / 7 (Phase 5 = real models, not run — as before), `Deck_check.py` 6 / 6:
    no regression.
  - **Next:** Phase B (additions).
- 2026-11-06 — **Phase B done** (handoff, owner: "كمل").
  - **D-B1 — room, not only a count:** measured (`Notebooks/_scratch/measure_additions.py`): three long Writer
    comments + even one addition run below the footer on slides 3–7, and warm-up weeks' slide 7 (customers table +
    watch rule + two comments) has no room for a short one. Rule: an addition is accepted while its slide has room
    by the renderer's own estimate (`render.comment_overflow`, at the smallest type), else `refused` "no room on
    slide n … shorten it, or shorten a comment with an edit in the same decision"; the cap of 2 per slide stays. The
    52 clean decks never overflow (so the check refuses nothing that worked before).
  - Code: `deck/validator.py` — `APPROVER`, `ADDITION_SLIDES` (3–9), `MAX_ADDITIONS` (2), V4 counts the Writer's
    bullets and the approver's apart (slide and cap rules for additions), `addition_evidence(evidence, slide)` (the
    slide's answered results; on slide 9 external ones only); `deck/render.py` — additions drawn as
    `txt:approver:<i>`, navy italic, text prefixed "Approver's addition: " (`APPROVER_MARK`), `comment_overflow`;
    `graphs/weekly_pack.approval` — additions placed after the slide's last bullet with `origin: "approver"`, refused
    before the Validator for slide 2 / 1 / 10, a third on a slide, no room; logged as `added` in the approval entry
    (→ `approval.json`); charts and `revise` still refused until Phases C / D.
  - Checks: `Weekly_pack_check.py` **Phase 7** (new): 10 steps on W23 / W5 — placed, re-validated, waiting again;
    slide 2 / third addition / > 300 chars / no room / charts / revise refused with their reasons; a 1 %-off number
    → V2 shown, fixed by an edit; published with two marked `txt:approver` shapes, V8 clean, `approval.json.added`
    → 7 / 8 (Phase 5 real models not run). `Deck_check.py` **Phase 7** (new): weeks 5 / 10 / 23 / 49 with an
    addition on each slide 3–9 → V1–V9 + V8 pass (slide 7 skipped for room in warm-up weeks 5 / 10), 16 / 16
    planted faults caught (V2 ×2, V4 ×2), 0 clean decks overflow → 7 / 7. Lint 0 / 0.
  - **Next:** Phase C (charts in the pack: `build_spec` reads the chart choices from the state, the 26-week fetch,
    the independent chart-field check of D-A2).
- 2026-11-06 — the owner (going to sleep): "كمل ال phases كلها ورا بعض … لو في اي مشكلة حاول تحلها بذكاء … ال quality و
  ال performance" — the remaining phases run in one go (memory: autonomous when the owner is away); decisions logged
  here as D-x items. The frontend plan runs in its own session (`docs/plans/Frontend_plan.md`, PROPOSED there).
- 2026-11-06 — **Phase C done** (handoff).
  - Code: `deck/render.py` — `_Spec(…, charts)`, `build_spec` / `render` / `comment_overflow(…, charts=None)`;
    `trend_window(evidence, weeks)` (a 26-week window = `kpi.trend_prev` + `kpi.trend`), `variance_rows(evidence,
    field, which)`; a variant names itself in a small muted caption above its chart (`tpl:trend.window`,
    `tpl:variance.choice`) and the chart moves down 0.3 in — the defaults draw exactly as before; the report-week
    marker is the last row marked `is_report_week` (week − 13's own row is in a 26-week window). `deck/style.py` —
    `AXIS_DAYS`, `AXIS_PCT`, **one fixed colour per measure** (`SERIES_OF`: billed blue, budget dashed grey,
    collected teal, receivables navy, overdue rust; D-C1: a series keeps its colour in every variant, the default
    deck unchanged). `deck/readback.py` — `chart_field_problems` (D-A2: each variant chart re-derived from the
    evidence apart from the renderer: series ↔ catalogue field, categories ↔ the window / the row choice, every
    point), run inside `validate_pptx(…, charts=None)`. `deck/charts.py` — week 1 has no WoW variance (refused).
    `graphs/weekly_pack.py` — state `charts` (non-default variants only), `chart_changes` (a change overlays the
    chart's current variant; back to the default drops it; a > 13-week window fetches `finance_kpi(trend, week − 13)`
    with the **run's** `RunContext`, stored as `kpi.trend_prev`, listed on the sources slide), the approval node gets
    the runtime, the interrupt payload carries `charts`, the validator / publisher render and read back with them,
    `run.json` keeps `charts` when not empty, the log entry keeps `charts`.
  - Measured first (`Notebooks/_scratch/proto_charts.py`): 132 variants on weeks 5 / 10 / 23 / 49 → 0 V8 problems
    in 49 s; the default variants' spec = no choice.
  - Checks: `Deck_check.py` **Phase 8** (new): every allowed variant on the four weeks read back (V8 + the
    independent check), the default spec equal on 52 weeks, 20 / 20 planted chart faults caught (swapped series, a
    point 1 % off, the window shifted a week, another measure under the chosen name, the bottom five for "top 5").
    `Weekly_pack_check.py` **Phase 8** (new): two variants → preview redrawn, waiting again; two units / 26 weeks
    before W26 / a chart without variants refused; back to the default drops it; published deck + `run.json`; on W30
    the CEO decides and the 26-week trend is fetched as the Finance manager (spied), = the tool called directly.
    Results: `Deck_check.py` 8 / 8 (first run: the test's own `deepcopy` of a spec failed on `RGBColor` — the fault
    test now copies only the chart's data), `Weekly_pack_check.py` Phase 8 passed (one expected reason text widened).
- 2026-11-06 — **Phase D done** (handoff). `graphs/weekly_pack.py`: section 7a — `revise` (caps D3: 2 a pack),
  `apply_analysis` (indexes = the notes as shown; replaces, removes from the end, adds; all or nothing; summary /
  driver wording only, context ≤ 3, caveats ≤ 6), `_screen` (trust.py), `STEER_NOTE` (one message after the
  history; the Insight agent's tool rounds counted from it: `steer_from`), the steered notes get the edits in
  `insight_notes` (`pending_analysis`; skipped edits reported in `revision`), `revise_failed` (**D-D1:** a re-draft
  that cannot be shown — a twice-invalid reply, V8, a failing fallback — restores the pack as it was before the revise
  and logs `revise_failed`; the validator then redraws its preview with no model call: a revise never loses a waiting
  pack), the approval node clears the restore point at every decision, `after_approval` → `insight_llm` (steer) or
  `writer`; payload + state `insight`, `redrafted`, `revision`. `deck/validator.py` `note_problems` (V1 / V2 / V6 /
  V7, V9, no NileGate figure in context). `Weekly_pack_check.py` **Phase 9**: note edits → 1 Writer call, 0 Insight
  (D2: no addition / variant kept); unbound number, injection-shaped steer, revise + edits, a third revise refused
  with 0 model calls; a steer → Insight + notes + Writer, the edit lands on the new notes; a Writer failing after
  the revise → restored. → **9 / 10** (Phase 5 = real models, not run).
- 2026-11-06 — **Phase E done.** API: `DecisionIn` takes `revise` + additions / charts / analysis edits / steer (the
  graph's `ApprovalDecision` rules → 422 before a run), the pack view adds `insight` / `charts` / `redrafted` /
  `revision`, `PACK_NODES` + the revise's nodes, `pack_decision` timeout 300 s, audit detail counts per kind. CLI
  `Weekly_pack.py resume --decision revise --add "4: …" --chart '{…}' --analysis file.json --steer "…"`; `show` prints
  the notes with indexes, the variants, re-draft / restore notes. G5 (`scheduling.approval_report`, D4): `edit_rate`
  counts edited or revised packs + `changes` per kind (text edits, additions, chart changes, analysis edits, steers,
  revises, restored). `Scheduler_check.py` expected report updated → 6 / 6. OpenAPI snapshot regenerated (28 paths).
- 2026-11-06 — **Phase F done.** `pipelines/agents/views.py` (`choose`: one structured `tools` call, the catalogue in
  the prompt, never data; `fetch`: `finance_kpi` as the asker, the deck's own windows / row choices), `pipelines/api/
  routers/views.py` (`GET /charts/catalogue`; `POST /views` — choice 200 / question 202 run, run kind `view` 30 / h,
  60 s; the `answer` event gains `view`), `View.py` (CLI + a one-slide PPTX read back), the frozen golden set
  `views_golden.jsonl` (30: 15 EN + 15 AR, written before the first run) and `Views_eval.py`. **D-F1:** run 1 failed
  before any call — Gemini's schema takes string enums only, `ViewChoice.weeks` was `Literal[4, 8, 13, 26]` → an int
  checked by the catalogue. Result `views_eval_2026-11-06.json`: **exact 0.9667** (EN 1.0, AR 0.9333 — v17 asked
  back instead of reading "أسبوع 52", a safe miss), ask-back 1.0, leakage 0, 30 calls → **D6 met**; not tuned on the
  frozen set. `Api_check.py` Phase 7 widened (variants + an addition, four 422 mixes, a revise with the pack's fake
  models: the Writer's node in the events, `redrafted`, no addition / variant kept) + **Phase 10** (catalogue, a view
  by choice = `finance_kpi` for W23 top 5 vs W22 and a 26-week trend, 403 / 422, a question → one fake call → the same
  view, no week → ask back) → **11 / 11**. **D-F2 (found, not this plan's):** one earlier `Api_check` run, made while
  `Weekly_pack_check` loaded the database, failed Phase 5 (conversation memory): the `clarify` turn's status was still
  NULL when read right after the `done` event — the turn row is written after the event. Re-run alone: 11 / 11. A real
  race under load in the FastAPI memory code (ADR-065), proposed as a follow-up. **Fixed 2026-11-06 (owner: "do it
  here"):** the race was wider than the read — the runner published `done`, *then* freed the conversation, *then*
  wrote the turn's status, so a follow-up asked at once could get 409, or be admitted and drop the last turn from
  its history (`status NOT IN (…)` is not true for NULL). `runs.Runner` now ends a run in a fixed order: `Run.claim()`
  (the thread or the time limit, the first wins) → `on_finish(state, result)` records the status → the conversation
  is freed → `done` / `failed` is published; a timed-out run is still told `failed` at once and its thread records
  "failed" later; a failed record is logged and keeps the answer. `Api_check` Phase 5 pins it on a private runner
  (success, error, time limit, a lost record).
- 2026-11-06 — **Phase G (model part) done; the visuals wait for the owner.** Power BI Desktop was open
  (`NileGate_Finance`, port 50974); through the Modeling MCP: measures `Trend Overdue SDR`, `Category Variance %`,
  `Category WoW Change SDR`; field parameters `Trend Series` and `Category Measure` (**G1 spike passed**: the
  DirectQuery model took them as small calculated tables, refreshed with Calculate); table `Compare Week` (DirectQuery
  on `finance.dim_week`, no relationship) + `Compare Week Label` and five "(compare week)" measures (the 4th DAX
  pattern, TREATAS); folder "7 Smart view"; 79 measures in `Weekly KPIs`. Checked against SQL: W23 and W22 by
  category (billed, variance %, WoW change — 13 rows each), the trend's overdue on W5 / W23 / W49 (31 points), W22's
  aging buckets via the compare table — all equal. **D-G1:** the visuals (series / measure slicers, the compare-week
  slicer, bookmarks "This week" / "13 weeks" / "Compare") are **not** built while the owner sleeps — ADR-048 (7) and
  the owner's rule: built on screen with him; the MCP changes are in Desktop's memory and **reach disk at his next
  Save** (Ctrl+S in Desktop; until then `powerbi/` is unchanged).
- 2026-11-06 — **Phase G (visuals) done with the owner** (owner chose a **new page**, not Revenue: the six
  reviewed pages stay untouched). Page **Smart View** (7th, `pages/a7c3e5f1b2d4c6e8f0a1`): the synced week slicer;
  three panels in one place, one shown at a time — *This week* (`Category Measure` slicer → a bar chart by vessel
  category on the field parameter), *13 weeks* (`Trend Series` slicer, multi-select → a line chart on the field
  parameter), *Compare* (`Compare Week` slicer, default W22 → billed by category and receivables by age, selected vs
  compare week, series renamed "Selected week" / "Compare week"); bookmarks **This week / 13 weeks / Compare**
  (Display + Current page, **Data off**: the reader's week and choices survive a switch) behind a bookmark
  navigator. **D-G2:** the page and its slicers / compare charts were written as PBIR files (modelled on the existing
  pages' `visual.json`, Desktop closed, then reopened), the field parameters bound and the bookmarks made on screen —
  synthetic drags into the field wells are not taken by Desktop, moving a field between wells is. Checked against
  SQL on W23 / W22: Crude Oil billed 2,114,698 / 0 and +411.83 % vs budget, Cruise Ships 703,818 / 1,774,700, every
  aging bucket (current 35,079,357 / 33,785,609 … 90+ 887,202 / 443,601), the trend's W11 / W16 billed and W23
  overdue — all equal. Saved 09:55. **The reader's view in words** stays the API (`POST /views`); the owner asked
  (2026-11-06) that the whole dashboard also be shown smart **in the frontend** — sent to the frontend plan as a
  change to approve there.
- 2026-11-06 — **Phase H (docs) done:** ADR-050 amendment 2, ADR-051 amendment 5, ADR-048 amendment 2, **ADR-066**,
  ADR-064 note; `ARCHITECTURE.md` (pack / deck / Power BI rows, the API, the ADR index), `docs/THREAT_MODEL.md` (the
  steer and the view question as LLM01 surfaces), `pipelines/README.md` (`View.py`, `Views_eval.py`, the widened
  checks). No-regression: `Stage1_eval.py` Phases 1–4 (fake, 0 calls) all passed; `Scheduler_check.py` 6 / 6;
  `Injection_eval.py` Phases 1–3 passed (frozen set unchanged); lint ratchet 0 / 0; OpenAPI snapshot = the app.
- **Open before the plan closes (owner):** ~~(1) Save in Power BI Desktop, then the visuals + bookmarks on screen
  (Phase G)~~ done 2026-11-06; ~~(2) the live check of the done-when — add a bullet, change a chart, revise once,
  approve~~ done 2026-11-07 on W14 (see below); (3) one commit of everything (C4). Then the plan is archived.
- 2026-11-07 — **Live check (2) done, on W14 run early at the owner's request** (`weekly_pack:live:2025-W14:1`, the
  scheduler's next week after W13:2; run as 6 = Finance manager). The pack came in DEGRADED (fallback; slide 9
  "External context unavailable", Tavily). (a) `edit` + `--add "4: …"` + `--chart` trend billed + collected over 8
  weeks → Validator passed, 0 problems, the bullet on slide 4 with `origin: approver`, the variant in `charts`, a new
  preview. (b) `revise --steer "…overdue rose while payments also rose…"` → one re-draft; summary[3] now explains it
  (4.87 M SDR newly due unpaid vs 3.98 M of older overdue collected); the addition and the chart variant gone as D2
  says (`charts: {}`), Validator passed, degraded smaller (1 replaced / 1 dropped vs 1 / 3). (c) `approve` →
  published `reports/2025-W14/` (`approval.json` holds the three decisions with the addition, the chart, the steer).
  Consequence: Monday 2026-11-09's task now builds W15.
