# Targeted revise and rare fallbacks — plan

## Implementation record

**Status: IMPLEMENTED (2026-11-16)** — P1–P6 done in the same side session; owner decisions T1–T4 (§6).

- **Done when — met:** `Deck_check.py` 9 / 9 ✅ (Phase 9: the V7 later-clause total); `Weekly_pack_check.py`
  10 / 11 ✅ (Phase 5 = real models, skipped; new Phase 10: the fallback's inline marks, the targeted revise with
  T1's slide rule, a steer, a short re-draft rewritten once); `Api_check.py` 12 / 12 ✅ (full-stack clone);
  `Approver_request_check.py` ✅; lint ratchet 0; `npm --prefix web run check` static ✅, Playwright ✅ (two timing
  flakes re-run alone 16 / 16). Both banners of `/packs` are gone; inline marks instead.
- **Evaluation (ADR-052 ninth use, T4):** `stage1_eval_2026-11-16_tr1.json` vs ec2 **"tie: keep"** — every gate in
  both runs, narrative recall 0.931 vs 0.9483 (−0.0173, limit 0.03); **degraded packs 6 / 22** (before 22 / 22),
  rewrites 37 vs 44; 134 flash-lite + 50 OpenRouter requests on 2026-11-16 (the second repeat resumed once from the
  caches after a Gemini 503 and OpenRouter's daily limit). Baselines unchanged.
- **Decisions recorded:** ADR-050 amendment 5 (the targeted revise; D2 superseded), ADR-051 amendment 14 (code
  drops tile-repeat comments before the Validator, the V7 fix, `origin: "code"` + `removed` shown inline),
  ADR-052 ninth use; ARCHITECTURE §2 / §7.
- **Deviations:** see Progress (the link-bullet drop also recorded in `removed`; `redrafted` kept beside
  `redrafted_slides`; a re-draft keeps `degraded` when code texts remain on kept slides; `Api_check`'s revise and
  proposal expectations).
- **Not changed (recorded):** the ADR-067 request interpreter's prompt line "the deck was drafted again" (its
  measured cache keys); the dashboards' "written by code" badge in `FinanceDashboard.tsx` (another plan's page).
- **Open (owner):** the commit once every plan in `docs/plans/` is closed.
  Uncertain: no real revise on a live pack was run (the fake-model phases prove the path).

---

**Status: APPROVED (2026-11-16)** — written in a side session started from the W17 session; decisions T1–T4 in §6
are the owner's (asked once, recommendation first; T1 and T4 chose the other option).

Owner's request (2026-11-16, after the live W17 pack): a revise must touch only the related slides, not the whole
pack, and the two banners of the web Reports page (`/packs`, `web/src/components/packs/PackReview.tsx`) must go
away because their causes are fixed:

1. "The deck was drafted again. Earlier edits and additions were not carried over — add again what you still want."
2. "Some texts were written by code because the writer's text did not pass its checks."

Touches: ADR-050 (amendment 2, D2: "nothing of the earlier draft is carried"), ADR-051 (amendment 3: the c4
fallback and `degraded`; amendment 12: code drops before the Validator), ADR-052 (a change that can move the
packs evaluation). No migration, no new dependency, no model or prompt change for the main draft.

## 1. What exists (inspected 2026-11-16)

- **Revise** (`pipelines/agents/graphs/weekly_pack.py` `revise()`, ADR-050 amendment 2): note edits and / or a
  steer → `insight_llm` (steer) or straight to `writer`; `draft_origin = "revision"`, `rewrites = 0`,
  `charts` reset to the defaults plus the revise's own chart choices, `redrafted = True`, `before_revise` kept for
  `revise_failed`. The Writer then runs its **full-deck** branch (`writer()`'s `else`): one `DeckDraft` call for all
  ten slides. Every approver edit, addition (`origin: "approver"`) and chart variant is gone — hence banner 1.
- **Fallback** (`fallback_draft()`, ADR-051 amendment 3): after `MAX_REWRITES = 2` failing rounds, the failing
  texts are replaced from `deck/sample.py` (slide 2 / 9 bullet by position, a slide title, the deck title, a V4
  slide wholly) or **dropped** (a comment on slides 3–8). `degraded` = indices into the *pre-fallback* draft
  (`replaced_bullets`, `dropped_bullets`, `code_slides`, `code_slide_titles`, `code_title`) — after the fallback
  the indices no longer point at the shown bullets, so the web can only show a page-level banner (banner 2).
- **Where notes reach slides** (`deck-style-guide` slide table, `validator.SLIDE_EVIDENCE`, `NOTE_SLIDE`): the
  summary points and caveats → slide 2; the drivers' explanations → slide 4 ("drivers with invoices"); context →
  slide 9. `insight.*` evidence (what a steer's new tool calls add) may be cited **only on slides 2 and 9**; slides
  3, 5, 6, 7, 8 cite `kpi.*` / `audit.*`, which a revise never changes.

## 2. Measurement: why the Writer still fails after its rewrites

Script (scratch, not kept): the live threads `weekly_pack:live:2025-W16:5` and `…W17:1` read from PostgreSQL
(`get_state_history`, read only) and the `s9` evaluation (the latest packs run, golden weeks × 2) **replayed from
its caches with 0 requests sent** (a request not in the cache = "diverged"), recording the problems handed to
`fallback_draft`.

- **`degraded` in every pack.** `stage1_eval_2026-11-15_s9_rescored_mf.json` (the first file that records it):
  22 / 22 packs degraded, 2 rewrites each. Live W16:5 and W17:1 (and W17's revise) too.
- Replay on today's tree: 16 packs reached the fallback, 6 diverged (ADR-051 amendment 13's three V9 rules refuse
  texts the cached rounds did not see — expected, a real run is needed to measure them).
- **The 57 problems left at the fallback (16 packs):**

| Problem left after two rewrites | Count | Packs | What it is |
|---|---|---|---|
| V9 rule 5 "repeats what the slide's tiles already show" | 25 | 13 / 16 | a comment whose slots are all tile fields; slide 8 (11: "checked N, none flagged" on a week the code table already says so), 3 (7), 6 (4), 7 (3) |
| V7 "`<total>` is the result's total, not `<date>`'s" (slide 9 transits) | 8 | 7 / 16 | **a Validator false alarm**: "averaged {week_mean_transits} daily calls, dipping to {…[2025-04-26]} on 2025-04-26" — `_named_rows` falls back to "the first row named after the number" even when that name is in a later clause |
| V7 a total vs an invoice named later (slide 8) | 3 | 1 | the same mechanism (`invoices_checked` vs "INV-…" later in the sentence) |
| V7 measure word ("calls it something else") | 4 | — | real (the field's family not named) |
| V9 "held / holding / stable" on a moved value | 4 | — | real |
| V5, V3, V2, V10, other V7 | 13 | — | real, one or two each |

- Only the first two kinds left: 5 of 16 packs (they would have passed with no fallback). Live W17's two
  remaining were one rule-5 slide-8 comment and one V7 row; W16:5's four were two rule-5, one V7 measure word, one
  V2 (`context.suez` has no field `transits`).
- Most fallback actions are **drops**, not code texts: in the 16 packs the fallback dropped 2–3 comments and
  replaced 0–1 bullets. So "Some texts were written by code" mostly means "a comment was removed".

## 3. Proposed design

### Part A — a targeted revise (owner: only the related slides are drafted again)

- **A1 Related slides, decided by code** (`revise_slides(before_notes, after_notes, steered)`): slide 2 always
  (the summary follows every change); slide 4 when a driver's explanation changed; slide 9 when a context item
  changed or a steer added `insight.*` results. Note edits: the changed items are known exactly; a steer: the old
  and new notes are compared item by item (text + evidence ids). Caveats → slide 2. Slides 1, 3, 5, 6, 7, 8, 10
  are never re-drafted (no revise changes their evidence). *(T1)*
- **A2 A partial Writer call**: a new structured schema `SlidesDraft` (`slide_titles` + `bullets`, for the named
  slides only). The prompt is the existing Writer prompt (same system message, same evidence / notes blocks) plus
  one block: "[redraft] write only slides <list>; the other slides stay as they are" and the current deck's other
  slides as context, so the summary agrees with them. Code merges: the Writer's bullets / titles of the named
  slides replace theirs; a text for another slide is dropped (one `normalized` line); `normalize_draft` runs as
  today. The main first draft and its prompt are unchanged (its cache keys do not move).
- **A3 What is kept**: every other slide's title and bullets **as they stand** (the approver's earlier edits
  included), every approver addition (also on a re-drafted slide, re-checked like any addition; one that no longer
  passes or fits is removed with a log line and an inline note), and the chart variants (the revise's own chart
  choices overlay them instead of resetting to the defaults). *(T2)*
- **A4 The Validator still checks the whole deck** (V1–V10 + V8). A failing round → the patch rewrite (it already
  sends only the failing texts) → the fallback → `revise_failed` restores the pack, as today.
- **A5 State and API**: `redrafted: bool` → `redrafted_slides: list[int]` (the last revise's slides) and
  `revision.slides`; the approval log's `revised` entry records them. `GET /packs/{thread}` returns
  `redrafted_slides`; the old `redrafted` is kept as `bool(redrafted_slides)` for one release of the client.
- **A6 Web**: banner 1 removed. The re-drafted slides carry an inline mark in the filmstrip and on the slide header
  ("Drafted again by the revise"); nothing on the other slides.

### Part B — rare fallbacks, and the code-written texts shown inline

- **B1 Code drops a redundant comment before the Validator** (`drop_tile_comments`, end of `normalize_draft`, the
  ADR-051 amendment 12 pattern): a Writer comment on slides 3–8 that V9 rule 5 would refuse (every number a slot of
  a tile field, no row named) is removed by code, one `normalized` line each. V4 allows 0–3 comments. This is what
  the fallback already does with it, one model round earlier and without marking the pack degraded (nothing code
  *wrote*). Human edits and additions are never dropped (rule 5 reads Writer slots only). *(T3)*
- **B2 V7 false alarm fixed** (`validator._named_rows`): a **result total** (a slot without a row) is attributed to
  a row only when the row is named in its own clause or before it in the sentence — never to a name in a later
  clause. Row slots keep today's rule. `Deck_check`: the W17 slide-9 sentence passes; "on 2025-04-26 the week
  averaged {total}" and "{total} on 2025-04-26" still fail; the 100 planted numbers and 34 planted claims still
  caught; the 52 clean decks still pass. *(T3)*
- **B3 Expected effect (estimate, not a measurement):** of the 57 problems left at the fallback, 36 disappear (25
  dropped earlier by B1, 11 no longer raised by B2); 5 of 16 replayed packs had nothing else left. Fewer problems
  also free the two rewrites for the real ones, so the true rate needs a real run (§5).
- **B4 Inline marks instead of banner 2**: the fallback marks what it wrote: a replaced bullet gets
  `origin: "code"` (a key outside the Writer's schema, like `"approver"`), a code slide title / deck title gets
  `origin: "code"` on its title entry, and a dropped comment leaves `degraded.dropped` = [{slide, text, rule}]
  (the text the approver lost, readable). The renderer, the Validator and V8 ignore `origin: "code"` (it is the
  Writer's slot form, checked as any Writer text). `degraded` keeps its summary for `run.json`, the dashboard row
  (`agent_state.pack_approved.degraded`) and `Stage1_eval.py`. Web: a small "Written by code" tag next to each
  such text (with the reason: "the writer's text failed <rule> after its rewrites"), and on a slide that lost a
  comment one muted line "Code removed a comment that failed its checks" with the text in a disclosure. Banner 2
  removed. B1's drops are listed the same way ("removed: it repeated the tiles") so the approver still sees them.
- **B5 Kept as is**: the fallback itself (the safety net), `MAX_REWRITES = 2`, the `fallback_share` line (a model
  outage, not a Writer failure — a different banner, not in scope), the dashboard's "written by code" badge in
  `FinanceDashboard.tsx` (the web dashboards plan's file).

Not proposed (recorded): a third rewrite (one more call per pack on the shared quota); relaxing rule 5 (it catches
real redundancy); Writer brief / skill lines about tiles and slide 8 — a Writer change, ADR-052 three runs per
side (≈ 1.5 provider days) — offered as T3's second option.

## 4. Phases

| Phase | Work | Proof |
|---|---|---|
| P1 | B2 `_named_rows` total-vs-later-clause; Deck_check Phase 9 (the W17 / s9 sentences pass, planted totals still fail) | `Deck_check.py` 9 / 9; lint ratchet |
| P2 | B1 `drop_tile_comments`; B4 `fallback_draft` marks (`origin: "code"`, `degraded.dropped`) | `Weekly_pack_check` Phase 3 (drop) + Phase 10a (a Writer that never passes: every code text marked, dropped texts listed); `Deck_check` 52 clean decks unchanged |
| P3 | A1–A5: `revise_slides`, `SlidesDraft`, the partial Writer branch + merge, kept edits / additions / charts, `redrafted_slides` | `Weekly_pack_check` Phase 10b: a pack with an edit on slide 6, an addition on slide 7 and a trend variant; revise a driver note → only slides 2 and 4 re-drafted, slide 6's edit / 7's addition / the chart kept byte-equal, whole deck V1–V10 + V8 pass; a steer → 2 (+ 9 when insight results added); a failing partial → fallback on those slides only; `revise_failed` still restores; Phase 9 updated |
| P4 | API `redrafted_slides`, the inline marks' fields; `docs/api/openapi.json` + the generated web client | `Api_check` (fake-model phases) |
| P5 | Web: both banners removed, inline "Drafted again" and "Written by code / removed" marks (EN + AR messages) | `npm --prefix web run check` (types, lint, unit, Playwright AR / EN); built-in browser screenshot of `/packs` |
| P6 | ADR-050 amendment 5, ADR-051 amendment 14, ARCHITECTURE §2 / §7, ROADMAP; the evaluation per T4 | docs |

## 5. Evaluation (ADR-052)

- The revise path is not part of the golden-week evaluation (no revise there); P3 is proven by the fake-model
  phases and, if the owner wants, one real revise on a live pack (2–4 Writer calls).
- B1 / B2 change what reaches the patch rounds, so the packs evaluation can move: **replay** first (0 requests:
  how many packs reach the fallback with the cached replies; diverged packs need fresh calls), then the real run
  `EVAL_SCOPE=packs` golden weeks × 2 vs ec2 (≈ 60–90 requests of flash-lite's 500 a day) — the owner's call on
  quota *(T4)*. Reported: `degraded_packs` (today 22 / 22), rewrites, every gate, narrative recall.

## 6. Decisions (owner)

Asked once 2026-11-16, answered the same day:

- **T1 related slides: "every slide that cites the same evidence"** (not the recommended note-kind map). Rule:
  slide 2 always; plus the changed note's own slide (driver → 4, context → 9); plus **every slide whose current
  Writer texts cite an evidence id the changed notes cite** (a bullet's `evidence_ids`, a slot in a bullet or a
  title). A steer's new `insight.*` results count as changed evidence (they may be cited only on 2 and 9).
  Caveats carry no ids → slide 2. Slide 10 has no Writer text. (A1 below is read with this rule.)
- **T2 the approver's work on a re-drafted slide: additions kept, edits replaced** (recommended) — A3 as written.
- **T3 making fallbacks rare: code only** (recommended) — B1 + B2, no prompt / model / skill change.
- **T4 the ADR-052 run: the real run now** (not the recommended replay-first): at the end of P5, `EVAL_SCOPE=packs`
  golden weeks × 2 against ec2 on the shared quota, judged by ADR-052; the replay is still printed first (0
  requests).

## 7. Files

`pipelines/agents/graphs/weekly_pack.py`, `graphs/models.py` (`SlidesDraft`), `deck/validator.py` (`_named_rows`),
`deck/render.py` / `deck/readback.py` only if `origin: "code"` needs a pass-through, `pipelines/api/routers/packs.py`,
`pipelines/api/schemas.py`, `docs/api/openapi.json`, `web/src/api/generated/*`, `web/src/components/packs/PackReview.tsx`
(+ its messages / tests), `pipelines/scripts/agents/Weekly_pack_check.py`, `Deck_check.py`, `Api_check.py`,
`docs/decisions.md`, `ARCHITECTURE.md`, `docs/ROADMAP.md`. Shared with other open plans: `PackReview.tsx`,
`packs.py`, `schemas.py` (web dashboards / frontend plans) — edited only in the parts named here.

## Progress / deviations

- 2026-11-16: plan written; measurement in §2 (scratch replay, 0 requests). Approved the same day (T1–T4, §6).
- P1 done: `_named_rows(total=…)`; `Deck_check.py` Phase 9 → 9 / 9 ✅.
- P2 done: `validator.repeats_tiles` (rule 5 as one helper, V9 unchanged), `weekly_pack.drop_tile_comments` at the end
  of `normalize_draft` (with the week), `fallback_draft` marks `origin: "code"` and fills `draft["removed"]`;
  `render_draft` fills `removed`; the V4 full rewrite's `[previous draft]` leaves `removed` out (`_writer_view`).
  Deviation: the link-bullet drop (amendment 12) also records its text in `removed`, so the approver sees it.
- P3 done: `revise_slides` / `SlidesDraft` / `merge_redraft` / `kept_slides`; an approver's edit is marked
  `edited` (code never normalizes or drops it); `asked_slides` / `slides_of` for the checks' fake Writers.
  Deviation: `redrafted` (bool) kept beside `redrafted_slides`; a re-draft that keeps earlier code texts on other
  slides keeps `degraded`.
- P4 done: `PackView.redrafted_slides` + the `draft` description; `docs/api/openapi.json`, Orval client and the
  allow-list regenerated. `Api_check` / `Approver_request_check` fakes answer `SlidesDraft`; Api_check's revise
  expectation now: slide 2 only, the chart variant and the slide-6 addition kept.
- P5 done: `PackReview.tsx` — both banners removed; "Written by code" tag on bullets / titles with origin code; "Code
  removed N texts from this slide" disclosure; the re-drafted slides marked in the filmstrip and on the slide; the
  revise wording "draft its related slides again". `npm --prefix web run check -- --static` all ✅;
  `packs.e2e.spec.ts` 10 / 10 (desktop; mobile skipped by design) incl. the new inline-marks test (axe 0).
- `Api_check` (full-stack clone, run by the JIT session on 2026-11-16): first run failed Phase 7 at "a proposal
  changed the pack" (the revise now keeps the chart variant) → fixed in `Api_check.py` (the edit sets a variance
  variant; the proposal check compares with the charts after the revise, so the 4-week trend request stays a real
  change) → re-run **12 / 12** ✅ (a PermissionError after the Final Checkpoint = two overlapping `tools/run.py`).
- `npm --prefix web run check`: every static suite ✅; Playwright 129 passed + 2 failed in `ask.e2e` / `auth.e2e`
  while three heavy jobs ran at once; both specs re-run alone: 16 / 16 ✅ (timing flakes, not this change).
- Not changed (recorded): the ADR-067 request interpreter's prompt line "the deck was drafted again" (its measured
  cache keys); `FinanceDashboard.tsx`'s "written by code" badge (the web dashboards plan's page).
- P6 done: the real run `tr1` (packs × 2 vs ec2): the first launch stopped in repeat 2 at 7 / 11 (Gemini 503,
  OpenRouter 50 / day), the re-launch resumed from the caches and finished → **"tie: keep"**, gates all met, degraded
  6 / 22, rewrites 37 (ADR-052 ninth use). ADR-050 am. 5, ADR-051 am. 14, ARCHITECTURE, ROADMAP updated; plan
  archived.
