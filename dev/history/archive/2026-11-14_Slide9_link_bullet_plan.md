# Plan — the traffic-link verdict never costs a rewrite as a slide-9 bullet

**Status: IMPLEMENTED (2026-11-14)** — archived as `docs/archive/2026-11-14_Slide9_link_bullet_plan.md`.

## Implementation record (2026-11-14)
- **Built:** `weekly_pack.drop_context_link_bullets` at the end of `normalize_draft` — a slide-9 Writer bullet citing
  `context.link` (evidence id or slot) is dropped before the Validator when another slide-9 Writer line remains,
  one `normalized` line each; as the only line it is kept and V5 decides. No prompt, V5, V10 or
  `traffic_claims.py` change. `Stage1_eval.py`: `EVAL_REPLAY_LABEL` + a guard that a replay never overwrites a
  results file.
- **Done-when:** (1) met; (2) met — `Weekly_pack_check` Phase 3 `link_bullet` (1 Writer call, 1 Validator pass,
  0 rewrites, one drop line) and the only-line case (kept, V5 refuses), 9 / 10 phases (Phase 5 = real models, on
  request); (3) met — `Deck_check` 8 / 8, `Traffic_claims_check` 5 phases, `Traffic_link_check` 6 / 6, lint 0 / 0;
  (4) met — the replay could not score the change (L2's stated case), the owner chose a real run: `s9` "tie: keep"
  vs ec2, every gate in both runs.
- **Deviations:** the replay stopped at the first pack (by design of L2); a wrong first count of the patches spent
  on the bullet was corrected the same day (11 of 340 fixes, not "nearly every patch"); `Weekly_pack_check` was run
  directly, not through `tools/run.py`, while the real run held a lock file (as D-TL-2).
- **Result, stated plainly:** the Writer still writes the bullet in most drafts (23 of 27 in `s9`); code drops it,
  and patch fixes about it went from 11 to 0. Rewrites stay two per pack — the patches' other problems (about seven
  texts each, mostly V9 "repeats the tiles"); not planned. Per-pack `degraded` is not in the results file: not
  measured.
- **Decisions kept:** ADR-051 amendment 12, ADR-052 eighth use.

---

**Status when approved: APPROVED (2026-11-14, owner: L1 code drop only, L2 replay of `tl2`, L3 one commit with the traffic-link
close — all as recommended)** — a follow-up of the traffic-billing link plan
(`docs/archive/2026-11-14_Traffic_billing_link_plan.md` §8, the live pack W16:5; ADR-051 amendment 11 (4)).
Touches ADR-051 (the deck, slots, the Validator), ADR-052 (acceptance). Does not change V5, V10 or
`pipelines/agents/traffic_claims.py`.

## 0. What is true today (verified 2026-11-14, read from the code and the W16:5 checkpoint history)

- The Insight notes carry the M17 verdict as a context line citing `context.link` (in W16:5: "No measurable link
  was found between the weekly invoice count and Suez transits over the observed weeks.").
- The Writer brief prints the slide → evidence table from `deck/validator.py` `SLIDE_EVIDENCE`. Slide 9 reads
  `context.*, insight.*`, so `context.link` **looks allowed** on slide 9 to the Writer.
- The Validator's first V5 check agrees (`allowed_on("context.link", 9)` is true), but its second V5 check refuses
  any slide-9 bullet that cites a PortPilot tool (`NILEGATE_TOOLS`: `context.link` is `finance_kpi`). The two
  checks contradict each other, and the brief shows only the first.
- In W16:5 the Writer put the verdict on slide 9 as a bullet; V5 refused it in all three rounds; a rewrite replaced
  it with a slot on a field that does not exist (V2); the fallback dropped it. The pack ended DEGRADED, and both
  rewrites ran on the OpenRouter fallback (50 requests a day).
- The verdict still reaches slide 9: the code-drawn link line (r lag 0 / lag 1 / threshold + "No measurable link")
  and, when the Writer writes it, the slide title (which may cite the slide's evidence, so V10 accepts it there).
- `SLIDE_EVIDENCE[9]` cannot simply drop `context.link`: the slide-9 title's link sentence would then be uncited
  and V10 would refuse it.

## 1. Goal and done-when

**Goal:** a slide-9 bullet built on `context.link` never reaches the Validator, so no rewrite is spent on it;
the verdict stays on slide 9 through the code-drawn line (and the title).

**Done when:**
1. `normalize_draft` (code, before the Validator) drops a Writer bullet on slide 9 that cites `context.link` (in
   its evidence ids or a slot), when at least one other slide-9 Writer bullet remains; the drop is one line in the
   state's `normalized` (shown to the approver as a code fix, saved in `run.json`). With no other slide-9 line it
   is kept, and V5 handles it as today (V4 needs one context line).
2. `Weekly_pack_check.py` Phase 3 gains a planted mode: a first draft with that bullet reaches the approval with
   **zero rewrites**, the bullet gone and the drop recorded; a unit case shows the only-line case kept and the
   Validator still refusing it (V5).
3. `Deck_check`, `Weekly_pack_check` (fake models), `Traffic_claims_check`, `Traffic_link_check` and the lint
   ratchet pass.
4. Acceptance (ADR-052) as the owner decides (§2 L2).

## 2. Owner decisions (asked once, clickable, recommendation first)

| # | Question | Recommended | Alternatives |
|---|---|---|---|
| L1 | The fix | **The code drop only** (no prompt changes: the Writer's requests stay byte-identical) | (b) The drop + one line in the Writer brief's slide-9 row ("the link verdict is drawn by code: never a slide-9 bullet"); changes every Writer request. (c) The brief line only (no guarantee) |
| L2 | Acceptance | **Replay `tl2` with `EVAL_REPLAY=1` (0 calls)**: the Writer's drafts are cached and identical; where the drop changes a draft that needed a patch, the replay stops on an uncached request and that is reported | (b) A fresh real-model packs run (≈ 150 calls, 2 repeats). (c) Fake-model checks only |
| L3 | Commit | **Together with the traffic-link close** (the owner's pending commit) | A separate commit |

## 3. Files

`pipelines/agents/graphs/weekly_pack.py` (`normalize_draft`), `pipelines/scripts/agents/Weekly_pack_check.py`
(Phase 3 mode + unit case), its checkpoint `pipelines/checkpoints/agents/Weekly_pack_check.md`, ADR-051
amendment 12, `ARCHITECTURE.md` (one sentence), `docs/ROADMAP.md`.

## 4. Progress / deviations

- 2026-11-14 — written PROPOSED; decisions asked; **APPROVED** as recommended (L1 code drop, L2 replay, L3 one commit).
- 2026-11-14 — implemented: `weekly_pack.drop_context_link_bullets`, called at the end of `normalize_draft`;
  `Weekly_pack_check.py` Phase 3 mode `link_bullet` + the only-line unit case (checkpoint updated).
  `Stage1_eval.py` gained `EVAL_REPLAY_LABEL` and a guard: a replay never overwrites a results file (the plain
  replay of `tl2` today would have overwritten `stage1_eval_2026-11-14_tl2_rescored.json`, the D-TL-14 record).
  - Checks: lint ratchet ruff 0 / pyright 0; `Deck_check` 8 / 8; `Traffic_claims_check` 5 phases;
    `Traffic_link_check` 6 / 6 — all 0 files changed.
  - **Replay of `tl2` (L2): stopped at the first pack, 0 calls, no results file** — repeat 1's first Writer
    patch request is in no cache. This is the case L2 named: the draft the cache holds carried the slide-9 link
    bullet, so the patch the run sent then listed it, and the patch now asked for does not.
  - **How often, read from the `tl2` caches (0 calls):** Writer drafts with a slide-9 bullet citing
    `context.link`: **10 of 11** (repeat 1) and **10 of 12** (repeat 2), never as the slide's only line (so code
    would drop every one). Patch replies: 22 and 22.
    - **Correction (same day):** a first count said "22 and 20 patches rewrite a text about the link" — that
      pattern (`link|transit`) matched the Suez transit lines too, so it was wrong. Counted per fix (a fix cites
      `context.link` or says "measurable link" / "too few weeks to measure"): **7 of 189 and 4 of 151 fixes**. The
      bullet was in almost every draft, but it was a small part of the rewrite work; W16:5, where it ended as one of
      the four last problems and sent a rewrite into a non-existent field, was the costly case.
  - Consequence: the replay cannot score this change; the owner chose a real-model packs run (L2's alternative b).
- 2026-11-14 — owner: "تشغيل حقيقي دلوقتي". Gemini usage 322, probe 6 / 6. **`s9` packs run COMPLETE:
  `stage1_eval_2026-11-14_s9.json`, ADR-052 vs ec2: "tie: keep"** — no gate regressed, narrative recall mean
  0.9655 vs 0.9483 (+0.0172; run 1 1.0, run 2 0.931). Both runs: 11 / 11 published, deck numbers 100 %, planted
  6 / 6, false alarms 0, claims 100 %, traceability 100 %. Calls 57 / 55, **0 fallbacks**, 2 failed calls (run 1),
  879 s.
  - **The fix, measured from the `s9` caches:** drafts with the slide-9 link bullet 13 of 15 and 10 of 12 (the
    Writer still writes it); patch fixes about the link **0 of 142 and 0 of 157** (`tl2`: 7 of 189, 4 of 151) —
    code drops every one before the Validator.
  - **Not changed by it:** rewrites stay 22 a run (two per pack, as in `tl2`): each patch still fixes about seven
    other texts (mostly V9 "repeats the tiles" and slot details). So this fix removes one avoidable problem and its
    worst case (W16:5); it does not lower the rewrite count — that is the Writer's general patch load, a separate
    question.
  - Results do not record `degraded` per pack, so how many packs ended degraded is **not measured** here.
