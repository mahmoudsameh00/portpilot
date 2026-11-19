# Plan — measuring the link between Suez traffic and NileGate's billing (by code, not by the model)

**Status: IMPLEMENTED (2026-11-14)** — archived as `docs/archive/2026-11-14_Traffic_billing_link_plan.md`.
Approved 2026-11-08; Phases 1–5 built 2026-11-08 → 09; Phase 6 (acceptance on the real models) 2026-11-12 → 14.
The product was renamed PortPilot on 2026-11-11 (ADR-068); this plan keeps the name it was written with.

## Implementation record (2026-11-14)

**What exists now**
- **Data:** `external.suez_transits_daily` (migration 025, IMF PortWatch, 371 days, level 1) loaded by
  `pipelines/scripts/structured/Suez_transits_loader.py`; the labelled scenario schema `finance_scenario`
  (migration 026, `Finance_scenario_generator.py`, planted amplification α = 1.6); the measure **M17**
  `kpi_traffic_link` in `finance`, `finance_test` and `finance_scenario` (migration 027: year-to-date Pearson r of
  the weekly invoice count against weekly Suez transits, lag 0 and 1, "link" when |r| ≥ the threshold, NULL
  before week 13); migration 028 (comments on 024's view columns, D-TL-5). `docs/finance_metrics.md` M17.
- **Tool / pack:** `finance_kpi` dataset `traffic_link`; the pack's evidence `context.link`; slide 9's code-drawn
  line (r lag 0 / lag 1 / threshold + a fixed verdict); `run.json` records `traffic_link`.
- **Guards:** Validator **V10** (ADR-051 amendment 8), then the shared policy `pipelines/agents/traffic_claims.py`
  on the deck, both Q&A paths, the approver's analysis edits and the Insight notes (amendment 9, stabilization
  R5 / R6), then the notes repair (amendment 11, D-TL-11).
- **Checks:** `Traffic_link_check.py` 6 / 6 (the views = an independent reference; planted series; 8 / 8 planted
  sentences refused); `Traffic_claims_check.py` 5 phases (66 pinned adversarial + 53 real-model sentences).

**Results against the done-when (§1)**

| # | Done-when | Result |
|---|---|---|
| 1 | The live answer written before the first run | Expected "no measurable link" (§4); measured: no link in any live week 13–52 (r(52) ≈ 0.02); scenario = link at 52 weeks (r 0.497) |
| 2 | Planted series: ≥ 95 % of planted links flagged, the false rate stated | Met (`Traffic_link_check` Phase 2; the false rate reported against the expected ≈ 10 %) |
| 3 | Planted sentences: 100 % caught | Met: V10 8 / 8; the shared policy 66 / 66 on every surface |
| 4 | No regression: planted findings 6 / 6 | Met: `tl2` 22 / 22 packs published, planted 6 / 6 in both runs, ADR-052 "keep (better)" vs ec2 |

**Phase 6 acceptance (L5 + D-TL-7), ADR-052 seventh use**

| Part | Result | File |
|---|---|---|
| Golden weeks × 2 (packs) | keep (better): all five gates, narrative recall 0.9828 vs 0.9483 | `stage1_eval_2026-11-13_tl2.json`, `…_tl2_rescored.json` |
| Finance Q&A EN + AR × 2 | tie: EN / AR 1.0, every gate | `stage1_eval_2026-11-13_tl3qa.json` |
| Stage 2 (supervisor) × 2 | done-when met; "reject" vs c1 by 0.0068 after the slot-form fix; closed by the owner, c1 stays | `stage2_eval_2026-11-14_tl3s2.json`, `…_tl3s2_rescored.json` |
| One live pack | `weekly_pack:live:2025-W16:5` **approved by the owner (web UI) and published**; publication verified, database sync `synced` | `reports/2025-W16/_publications/9f145f3119d44e6a903736a7c6913ba7/` |

**Deviations (detail in §8)**
- **D-TL-1** §0 corrected: V9 rule 1 already refused external-cause words; V10 extends it. **D-TL-3** a stronger,
  labelled planted link (α = 1.6) instead of the natural scenario (r ≈ 0.33, found in 66 % of draws).
  **D-TL-4** week numbers use `floor` (a truncation bug caught in a dry run). **D-TL-5** migration 028.
  **D-TL-6** the `finance_test` twin swaps the 4 test weeks into the live series. **D-TL-7** acceptance widened
  from L5 to golden weeks × 2 + the full Q&A × 2. **D-TL-9** three skill bodies shortened under the 1,200-token cap.
- **D-TL-10** the evaluation reads the old / new product name as equal in frozen text. **D-TL-11** the notes-stage
  guard repaired: true denials accepted, a refused sentence replaced by the fixed M17 wording instead of stopping
  the pack (the first real run `tl1` lost 7 of 11 packs to it). **D-TL-12** two scorer rules widened + `EVAL_REPLAY=1`.
  **D-TL-13** the former company name in the two Q&A briefs; a citation's page number allowed. **D-TL-14** two
  slot-form rules, the supervisor's answers only. **D-TL-15** Stage 2 closed on its done-when.
- Acceptance took three days, not one run: Gemini flash-lite had long 503 spells, the OpenRouter fallback has 50
  requests a day, and two unattended overnight runners died with the machine.

**Decisions kept:** ADR-051 amendments 8 / 9 / 11, ADR-052 seventh use, notes on ADR-059 and ADR-068.

**Known limits and what was not verified**
- The claim guard is a bounded pattern policy: a new paraphrase can be refused (cost: one sentence replaced).
- The live pack was **degraded**: after two rewrites (both on the fallback model — Gemini answered 503) code
  dropped three bullets. One was the Writer's "no measurable link" sentence as a slide-9 bullet, which V5 refuses;
  the verdict is on the slide through the code-drawn line and the title. The notes repair of D-TL-11 did not
  fire in the live pack (the model wrote the fixed wording itself), so it is proven by the replay and `tl2`, not
  by this pack. Not changed here: the brief / skill does not tell the Writer to leave the link off slide 9's bullets.
- Not opened : the published `deck.pptx` slide by slide (the preview of the same draft was), the Power BI
  "Approved Pack" page, the web UI screens of the approval.
- Code comments, the two manifests (`suez_transits_manifest.json`, `finance_scenario_manifest.json`), the two
  script checkpoints and migrations 025–027 still name this plan by its old path `docs/plans/…`; they are left
  as written (the manifests are hashed artifacts of their scripts, the migrations are applied).

---

**Status when approved: APPROVED (2026-11-08, owner: "موافق على الربط")** — written on the owner's request ("أيوه، اكتب اقتراح") after the question "do invoice
prices and accounts move with Suez traffic and the news, and can the project relate that evidence?". Queued behind
`Pack_external_context_plan.md` (APPROVED 2026-11-08, in progress): both touch `pipelines/agents/graphs/weekly_pack.py`
and the deck Validator, so this plan starts only after that one closes. No code before the owner approves this plan.
`docs/plans/` also holds `Frontend_plan.md` (another session).
Touches ADR-004 (toll pricing), ADR-046 (synthetic finance data), ADR-047 (KPIs only in the `finance` views),
ADR-050 / ADR-051 (the pack graph, slide evidence, the Validator), ADR-052 (acceptance), ADR-056 (no live AIS),
ADR-006 / `docs/rbac_mapping.md` (a new level-1 table).

## 0. What is true today (existing, verified 2026-11-08)

- **Invoice amount** = the progressive toll bands of the tariff (`compute_toll`, ADR-004) for the vessel's category,
  SCNT and condition. No input reads Suez traffic or news.
- **Invoice dates** are drawn uniformly over 2025: `date(2025, 1, 1) + timedelta(days=random.randint(0, 364))`
  (`pipelines/scripts/synthetic/SyntheticGenerator.py:306`, seed 42). The weekly invoice count therefore does not
  follow the real traffic. The weekly budget is a planning model (fleet × 2.0 transits × median laden toll, seasonal
  ±6 %, `Finance_generator.py` R6), not fitted to the traffic either.
- **Consequence:** on the live data the expected link between NileGate's billing and Suez traffic is about zero. Any
  sentence linking them would be false.
- **Today's guard (corrected 2026-11-08 after a graph trace):** the skill `weekly-variance-analysis` says
  "Correlation is not cause: Suez transits or news are context on slide 9; never write that they caused a NileGate
  change unless a document or the data shows the link". **And the Validator does enforce part of it:**
  - V9 rule 1 (`pipelines/agents/deck/validator.py` `claim_problems`, `EXTERNAL_RE`) refuses any external-cause
    word on slides 1–8: Red Sea, Houthis, war, conflict, crisis, sanctions, attacks, rerouting, Cape of Good Hope,
    disruption, tensions, global trade / demand, freight rates, shipping markets.
  - Its gaps: (a) the words "Suez", "transits" and "traffic" are not in the list, so "billing fell as Suez transits
    dropped" passes; (b) it is a ban, so it can never allow a measured link; (c) it guards the deck only, not the Q&A
    answers.
  - No dataset exists that could "show the link".
- **PortWatch** daily Suez transits, with per-type counts (`n_total`, `n_container`, `n_tanker`, `n_dry_bulk`,
  `n_general_cargo`, `n_roro`, …), are fetched by `external.suez_transits` and cached as JSON in
  `Data/processed/agents/tool_cache/`. They are not in PostgreSQL, so no SQL view can join them to billing today.
- **Rule:** completed tables are never regenerated (the project rules, development rule 2). The golden weeks, the Stage 1
  baselines, the hand-checked weeks (P2-7) and the published packs W12–W14 all rest on the current invoices.

## 1. Goal and done-when

**Goal:** the pack and the Q&A can say, with a number computed by code, whether NileGate's weekly billing moves with
Suez traffic: "moves with the traffic (r = …)" or "no measurable link (r = …)". A sentence that links the two must
cite that number, and the Validator enforces it.

**Done when:**
1. On the live data the measure answers, and the answer is written down **before** the first run (expected: no
   measurable link, because the dates are uniform). Same discipline as the ETA rule R (P11-3).
2. A check with planted series (pure code, no database) flags ≥ 95 % of the planted links (r ≈ 0.6) and at most the
   stated false rate on independent series (§3f).
3. Planted model sentences that claim a link without citing the measure, or against it, are rejected by the
   Validator: 100 % caught.
4. No regression: the golden weeks' planted findings stay 6 / 6, as in the c5b baseline.

## 2. Owner decisions (asked once, as clickable choices, recommendation first)

| # | Question | Recommended | Alternatives |
|---|---|---|---|
| L1 | Which data | **Measure on the live data as it is** (honest answer: no link) | (b) A separate scenario schema `finance_scenario` whose invoice dates follow PortWatch, live data untouched: shows a positive case from start to end, at the cost of a second copy of the views. (c) Regenerate the 2025 invoices: breaks the golden weeks, baselines, hand-checked weeks and published packs (not recommended) |
| L2 | Where the PortWatch series lives | **Migration 025: table `external.suez_transits_daily` (level 1, public), filled by a loader script; the measure is a SQL view** (one definition, ADR-047; Power BI can show it) | Computed in Python from the JSON cache (no migration, but not in SQL and not in Power BI, which conflicts with ADR-047) |
| L3 | The measure | **Pearson `corr()` of the weekly invoice count vs the weekly Suez transits, year to date (weeks 1…w, at least 13), at lag 0 and lag 1 week; "link" when \|r\| ≥ 2 / √n** (≈ the 5 % two-sided threshold; checkable by hand) | (b) Spearman + a permutation test in Python (more exact, not in SQL, not checkable by hand). (c) Also per vessel category vs PortWatch per type (containerships ↔ `n_container`, …): more insight, more tests → a second stage |
| L4 | Use in the pack | **A dataset `context.link` in the Insight digest + Validator rule V10:** a sentence that links billing to Suez, traffic, the Red Sea or the news must cite `context.link`, and the measure must say "link" | Only a line on slide 9, with no Validator rule |
| L5 | Acceptance (ADR-052) | **The new check script (planted series + planted sentences) + golden weeks once + one live pack**; the Q&A golden set is not re-run (the Q&A agent does not change) | Full ADR-052 (golden weeks + Q&A, EN + AR, twice) |
| L6 | Commit | **One commit when this plan closes** | — |

**Owner's answers (2026-11-08):** **L1 = a separate scenario dataset** (over the recommended "live data as it is"):
the live data stays untouched and is measured too, so the measure is shown on both a case without a link (live) and
a case with one (scenario). L2 migration 025 + a SQL view (recommended); L4 dataset + Validator V10 (recommended).
L3, L5 and L6 were not asked: they take the recommended answer unless the owner changes them when approving.
The plan is still PROPOSED: the owner approves the whole plan before any code.

## 3. Design (PROPOSED; assumes the recommended answers)

### 3a. Migration 025 — `external.suez_transits_daily`
- Schema `external` (public data, sensitivity level 1, owner department Operations). Columns: `date` (PK) and the
  PortWatch counts of `TRANSIT_FIELDS`, `source`, `retrieved_at`.
- Read grants: `ports_agent`, `ports_bi`, `nilegate_reader`-style read-only logins as today. Writer: the loader only.
- A row in `docs/rbac_mapping.md`; `db/schema_snapshot.sql` and `db/verify_readonly.sql` refreshed after the
  migration (by the owner, `db/README.md`).

### 3b. Loader `pipelines/scripts/structured/Suez_transits_loader.py`
- Reads PortWatch (the same URL as `external.PORTWATCH_URL`) for 2024-12-23 … 2025-12-28, so that lag 1 has the week
  before week 1. Upsert by date: safe to re-run.
- Validation cells: 371 days with no gap; counts ≥ 0; `n_total` = the sum of the types where PortWatch gives them;
  the W14 days equal the tool cache's W14 result.
- A Final Checkpoint narrative in `pipelines/checkpoints/structured/`.

### 3b'. The scenario dataset (L1) — schema `finance_scenario`
- **Idea:** the same invoices (amount, vessel, customer, category) and the same budget, but **re-dated** so that the
  weekly invoice count follows the real Suez traffic of 2025. The live `finance` schema and its tables are not
  touched (development rule 2).
- **Generator** `pipelines/scripts/synthetic/Finance_scenario_generator.py` (seeded, like `Finance_generator.py`):
  1. Weekly weights = the weekly sum of `external.suez_transits_daily.n_total` over ISO weeks 1–52 of 2025.
  2. The 2025 invoices are spread over the 52 weeks by a multinomial draw with these weights; inside a week the day
     is uniform. Optional refinement (asked at Phase 2): per vessel category with the matching PortWatch type.
  3. Each payment keeps its own delay: new `paid_date` = new `invoice_date` + (old `paid_date` − old
     `invoice_date`), so terms, delays and punctuality are kept and only the timing moves.
  4. Output: CSV files in `Data/processed/synthetic/` + a manifest (SHA-256), loaded by migration 026.
- **Migration 026:** schema `finance_scenario` = the scenario tables + the KPI views as a twin of `finance` (the
  migration 017 / 022 pattern for `finance_test`), plus `kpi_traffic_link`. Level 2 / Finance. Read by the check,
  by Power BI (a "scenario" switch is optional) and by the pack's dataset `scenario` (the same mechanism that sends
  `test` to `finance_test`).
- **Written before generating:** the expected r in the scenario comes from the size of the weekly traffic swings
  against the count noise (about 19 invoices a week). Phase 1 measures the weekly swing of the real 2025 transits
  and writes the expected r down before the generator runs.
- **Honesty rule:** every scenario output (slide, Power BI page, answer) says "scenario" in its title or label.
  Scenario numbers never appear in a live pack.

### 3c. View `finance.kpi_traffic_link` (and its `finance_test` and `finance_scenario` twins, the migration 017 pattern)
- One row per report week w: `invoices_billed` (from `kpi_weekly`), `suez_transits_week` (the sum over Monday–Sunday),
  `n_weeks` (= w), `r_lag0`, `r_lag1` (over weeks 1…w; lag 1 = the transits of the week before),
  `r_threshold` = 2 / √n, `link` ∈ {`link`, `no_link`}.
- NULL in weeks 1–12, the same warm-up spirit as `is_warmup`.
- `docs/finance_metrics.md`: a new metric M17 with this definition, and a pandas reference in
  `Finance_views_check.py`.

### 3d. Tool
- One more dataset in the Stage 1 finance tool (level 2 / Finance, since it joins billing): `traffic_link` for a
  week. The Q&A can then answer "did Suez traffic move with our billing up to week 30?".

### 3e. Pack
- The Insight digest gets `context.link`.
- The skill `weekly-variance-analysis` replaces the words-only rule with: "a link sentence cites `context.link`;
  'moves with' only when `link = link`; never 'caused by'". The skill is reviewed by the owner (as for every skill
  change).
- Slide 9 gets one code-drawn line, for example: "Billing vs Suez transits, weeks 1–w: r = x (same week) / y (one
  week later); a link needs |r| ≥ z → no measurable link."

### 3f. Validator V10 + check `pipelines/scripts/agents/Traffic_link_check.py`
- **V10 (extends V9 rule 1, does not duplicate it):**
  - A sentence with a link word (because of, driven by, due to, linked to, reflects, in line with, …) next to Suez,
    transits, traffic, the Red Sea or the news must cite `context.link`, and the measure must be `link`. Otherwise
    the sentence is rejected. "Caused by" is always rejected.
  - V9 rule 1's ban on external words in slides 1–8 stays. V10 only adds a cited, measured "moves with" sentence as
    its one exception, and adds "Suez / transits / traffic" to the words it watches.
  - The Q&A answers get the same check through the supervisor's answer check (a decision at Phase 5).
- **The check:**
  1. The view = the pandas reference, for every week of `finance` and `finance_test`.
  2. Planted series (seeded): 200 series correlated at r ≈ 0.6 → flag rate ≥ 95 %; 200 independent series → the
     false rate is reported against the expected ≈ 10 % (two lags at 5 % each; stated, not hidden).
  3. Planted sentences for V10, all caught.

### 3g. Phases

Phases 1–3 touch no file of the external-context plan, so they may start before that plan closes. Phases 4–6 wait
for it (`weekly_pack.py`, the digest, the Validator, slide 9, the skill).

| Phase | What | Done when |
|---|---|---|
| 1 | Migration 025 + `Suez_transits_loader.py`; the weekly swing of the real 2025 transits and the scenario's expected r written down (§3b', §4) | loader validations pass; the expected r is recorded in Progress |
| 2 | `Finance_scenario_generator.py` + migration 026 (`finance_scenario` tables + KPI views) | the generator's validations pass; the scenario views = a pandas reference |
| 3 | `kpi_traffic_link` in `finance`, `finance_test` and `finance_scenario`; M17 in `docs/finance_metrics.md`; `Finance_views_check.py`; check parts 1–2 (view = reference, planted series) | both datasets give their expected answers (§4) |
| 4 | The finance tool dataset `traffic_link`; the pack's digest `context.link`; dataset `scenario` for the pack; slide 9 line | code + lint clean |
| 5 | Validator V10 + the skill edit (**reviewed by the owner**) + check part 3 (planted sentences) | all caught |
| 6 | Acceptance (L5): golden weeks once + one live pack (+ one scenario pack); ADR, `ARCHITECTURE.md`, ROADMAP, archive | gates held; the owner's commit |

Migrations 025 / 026 are applied by the owner (`db/README.md`), or  after the owner says so.

## 4. Expected result (written before measuring)

- **Live data:** **no measurable link** in every week from 13 to 52. The invoice dates are uniform, so |r| should
  stay under 2 / √n. A week that comes out as `link` would be chance (≈ 10 % of the weeks with two lags), so the
  slide shows the threshold next to r.
- **Scenario data:** **a link at lag 0** from the week where n is large enough, with the expected r written down in
  Phase 1 (§3b').
- The same view gives opposite answers on the two datasets. That shows the measure finds a link only where one
  exists.

## 5. Out of scope

- **The price effect** (tariff changes, rebates or surcharges after a crisis): it comes from the tariff documents and
  the Notes rule (migration 019 → `manual_review`), not from traffic.
- **Causation:** a correlation is still not a cause. The flag says "moves with", never "caused by".
- Live AIS (ADR-056). News as a number: news stays untrusted text.

## 6. Risks

- **Low power:** n ≤ 52 weeks and about 19 invoices a week. |r| must reach 0.55 at n = 13 and 0.28 at n = 52. A
  real but weak link can be missed, and the slide says so.
- **Two lags = two tests:** the false rate roughly doubles. It is stated on the slide and in the check, not hidden.
- **PortWatch revises past days:** the loader stores `retrieved_at`, and a re-run is a choice, not automatic.
- **Overlap with the external-context plan** (`weekly_pack.py`, the digest, the Validator): this plan waits for it.

## 7. Files (planned)

`db/migrations/025_suez_transits_link.sql` · `db/migrations/026_finance_scenario.sql` ·
`pipelines/scripts/synthetic/Finance_scenario_generator.py` (+ its CSVs, manifest and checkpoint) ·
`pipelines/scripts/structured/Suez_transits_loader.py` +
`pipelines/checkpoints/structured/Suez_transits_loader.md` · `docs/finance_metrics.md` (M17) ·
`pipelines/scripts/finance/Finance_views_check.py` · the Stage 1 finance tool (dataset `traffic_link`) ·
`pipelines/agents/graphs/weekly_pack.py` (digest) · `pipelines/agents/deck/validator.py` (V10) +
`pipelines/agents/deck/render.py` (slide 9 line) · `pipelines/agents/skills/weekly-variance-analysis/SKILL.md` ·
`pipelines/scripts/agents/Traffic_link_check.py` · `docs/rbac_mapping.md` · `ARCHITECTURE.md` · `docs/ROADMAP.md` ·
`docs/decisions.md` (a new ADR at close).

## 8. Progress / deviations

- 2026-11-08 — written PROPOSED; L1 / L2 / L4 asked as clickable choices: **L1 = a scenario dataset** (over the
  recommended "live data as it is"), L2 and L4 as recommended; L3 / L5 / L6 = the recommended answers. §3b' (the
  scenario dataset) added.
- 2026-11-08 — **APPROVED** (owner: "موافق على الربط"). §3g phases added. The external-context plan is in its Phase C
  (candidate ec2 running): Phases 1–3 here touch none of its files; Phases 4–6 wait for it to close.
- 2026-11-08 — **Correction (D-TL-1):** a the local graph tool trace (`claim_problems` ↔ the route-advice cost rule P10-1) showed
  that V9 rule 1 already refuses external-cause words on slides 1–8. §0 said "the Validator does not check it": wrong.
  §0 and §3f are corrected; V10 now extends V9 rule 1 instead of adding a parallel rule.
- 2026-11-08 — **Phase 1 code done** (owner: "ابدء"): `pipelines/scripts/structured/Suez_transits_loader.py`, 6 / 6 ✅,
  re-run changes 0 files, ruff + pyright clean; checkpoint `pipelines/checkpoints/structured/Suez_transits_loader.md`.
  Outputs: `Data/processed/structured/{portwatch_suez_raw.json, suez_transits_daily.csv, suez_transits_manifest.json}`
  and `db/migrations/025_suez_transits.sql` (**not applied yet**). 371 days; the type split adds up exactly; all 371
  days equal the agent tool's cache.
  - **D-TL-2:** `tools/run.py` cannot hash a lock file held by the running evaluation (`llm_cache/openrouter/locks`),
    so the script was run directly with a SHA-256 before / after check. `run.py` was not changed.
  - **Expected r, recorded before the scenario (§3b' / §4):** the weekly transits swing CV 7.99 % (217 … 315). In
    the scenario as designed, r ≈ 0.33 at 52 weeks, and the rule says "link" in only 66 % of draws (11 % at 13
    weeks); uniform (live-like) data: r ≈ 0, false "link" 4–6 %. **Open for the owner (D-TL-3):** keep the honest
    scenario (a weak, often-missed link), or plant a stronger one before Phase 2.
  - **D-TL-3 answered (owner):** "a stronger planted link, labelled": the scenario's weekly weights become
    mean + α × (transits − mean), with α the smallest factor that makes the rule say "link" in ≥ 95 % of draws at
    52 weeks. α is computed in Phase 2 (seeded), written into the scenario's name / comments, and the natural
    scenario's result (α = 1: 66 %) stays on record here and in the loader's manifest.
  - **025 APPLIED 2026-11-08** (owner: "dry run وبعدين طبّقها"): dry run rolled back first (371 rows); applied with 0
    errors; `ANALYZE`; 371 rows, Σ n_total 14263, ports_readonly reads and cannot insert. `db/verify_readonly.sql` gained
    §26; `docs/rbac_mapping.md` row added; `db/README.md` row added. **Open (owner):** the snapshot refresh and the
    audit run. The assistant's combined command for both was declined, so the owner runs them (`db/README.md`
    commands; report `db/audit/2026-11-08_after_025_report.txt`).
  - **Next:** Phase 2: `Finance_scenario_generator.py` (α search, multinomial re-dating, payments keep their delay)
    + migration 026 (`finance_scenario`).
- 2026-11-08 — **Phase 2 code done** (owner: "كمّل Phase 2"): `pipelines/scripts/synthetic/Finance_scenario_generator.py`,
  7 ✅ (Phase 7 pending until 026 is applied), re-run changes 0 files, ruff + pyright clean. **α = 1.6**: the smallest
  value on a 0.1 grid with link rate ≥ 95 % (0.972; natural α = 1: 0.663). The draw (seed 43) has weekly counts 7 … 31
  and realized r of 0.506 at 13 weeks (below 0.555: no link yet), 0.468 at 26 and 0.497 at 52 (link). Payments keep
  their delays (20 … 160 days, the sorted lists identical); 176 scenario payments fall after 2025-12-28. Migration
  026 is generated from the live view definitions (`pg_get_viewdef` with an empty search_path, so every name is
  qualified; `public.invoices` / `public.payments` / the eight finance twins are rewritten). It holds scenario_info,
  invoices, payments and 8 twin views, every comment labelled with α.
  - **Dry run (rolled back):** 0 errors. Scenario vs live `kpi_weekly`: 996 invoices and 267,892,000.68 SDR billed in
    both (only the timing moves); collected 216.1 M vs 227.2 M (payments pushed past week 52). Trend 598 rows = live.
    In the database, r(invoices_billed, weekly transits) = **0.497 scenario** (= Python) and **0.020 live**.
  - **D-TL-4 (bug caught in the dry run):** in SQL, `(date − 2024-12-30) / 7` truncates toward zero, so days −6 … −1
    (the lag week) fell into week 1 (a first probe gave r 0.265). Week numbers must use `floor(… / 7.0)`. Fixed in
    `verify_readonly.sql` §26 (it would have shown 51 full weeks, not 53). **Phase 3's view must use floor** (and the
    check compares it with Python).
  - **Next:** the owner's word on applying 026; then Phase 7 of the generator (the views = a pandas reference), the
    snapshot / audit, and Phase 3.
- 2026-11-08 — **Phase 2 done: 026 APPLIED** (owner: "أيوه، طبّقها"): 0 errors (181 COMMENT, 3 tables, 1 + 1,000 +
  994 rows, 8 views, 2 GRANT); `ANALYZE` on the three tables. Generator 8 / 8 ✅ including **Phase 7: the scenario
  views = the pandas reference on 52 weeks** (billed, count, collected, payments, AR, overdue: max |diff| 0); a re-run
  changes 0 files. `verify_readonly.sql` §27 added; §26 and §27 run on their own give the expected rows (§26: 53 full
  weeks after D-TL-4). `db/README.md` rows for 025 / 026 and `docs/rbac_mapping.md` row for `finance_scenario.*`
  added.
  - **Open (owner):** the snapshot refresh and the full audit (`db/audit/2026-11-08_after_026_report.txt`), now
    covering 025 + 026.
  - **Next: Phase 3:** `kpi_traffic_link` in `finance`, `finance_test` and `finance_scenario` (week numbers with
    `floor`; YTD Pearson r at lag 0 / 1; threshold 2 / √n; NULL in weeks 1–12) as migration 027; M17 in
    `docs/finance_metrics.md`; the reference in `Finance_views_check.py`; check parts 1–2. Expected: live = no link
    (r(52) ≈ 0.02 in the dry-run probe), scenario = link from week 26 (r 0.468 / 0.497).
- 2026-11-08 / 09 — **Phase 3 done** (owner: "كمّل Phase 3", then "أيوه، طبّق وشغّل" after Docker Desktop was
  restarted): `db/migrations/027_kpi_traffic_link.sql` (written by hand; dry run first) **APPLIED 2026-11-09**, 0
  errors; `finance_bi` reads only the live view.
  - **D-TL-6:** `finance_test.kpi_weekly` holds only the 4 test weeks, so its twin uses the live weeks with those 4
    counts swapped for the copy's (the migration 017 pattern). Week 23 has 30 invoices in the copy vs 29 live.
  - `pipelines/scripts/agents/Traffic_link_check.py` **5 / 5 ✅**:
    - The views = an independent reference (counts from the base invoice dates, transits from the loader's CSV, the
      rule in numpy): 0 mismatches on 3 × 52 weeks × 5 columns. The first run reported 36 false "mismatches": pandas
      turns a NULL `link` into NaN; the comparison was fixed, not the view.
    - Reviewed snapshot: live 0 link weeks of 40, test 0, scenario 29, the scenario's first link week 24 (the value
      written before the run was an estimate; the run printed 24), live r(52) 0.020, scenario 0.497.
    - Planted series at 52 weeks (seed 7, 200 each): lag 0 → 100 % flagged, lag 1 → 100 %, the lag named right
      every time; independent series → 5 % flagged (stated expectation ≈ 10 %).
  - `docs/finance_metrics.md` M17 added. `verify_readonly.sql` §28 added (expected = the run); §27 now expects 9
    views. `db/README.md` row for 027 added.
  - **D-TL-5 (pre-existing, found here):** `Finance_views_check.py` had failed since migration 024: its expected list
    lacked the three `pack_*` views. The list is updated (+ `kpi_traffic_link`). It now stops one assert later, at
    "views / columns without COMMENT: (0, 23)". All 23 are columns of 024's `pack_approved_summary` (7),
    `pack_trend_long` (9) and `pack_variance_long` (7); `kpi_traffic_link` has 0. The check was not weakened. **Open
    for the owner:** a small comments-only migration 028 for those 23 columns (outside this plan's scope), or leave
    it.
  - **Open (owner):** the snapshot refresh and the full audit (025–027).
  - **Next:** Phases 4–6 wait for `Pack_external_context_plan.md` to close (the pack's digest, slide 9, V10, the
    skill, acceptance).
- 2026-11-09 — **D-TL-5 closed** (owner: "اكتب وطبّق migration 028"): `db/migrations/028_pack_views_column_comments.sql`
  (comments only, 23 columns of 024's three views; dry run first) applied, 0 errors; `Finance_views_check.py` **8 / 8**.
  The owner also chose to close the external-context plan here, so Phases 4–6 can start: the ec2 evaluation had
  finished 2026-11-08 15:39 with every gate held in both runs, and was not yet recorded in that plan.
- 2026-11-09 — the external-context plan closed and archived (`docs/archive/2026-11-09_Pack_external_context_plan.md`;
  its Phase E needed two fixes, D-EC-5 / D-EC-6, see there).
- 2026-11-09 — **Phase 4 code done.** Owner decisions asked as clickable choices:
  - **D-TL-7:** "the pack and the Q&A together". The tool dataset is added now, and the full Q&A evaluation (EN + AR,
    twice) joins Phase 6's acceptance (L5 widened).
  - **D-TL-8:** "defer" the scenario pack (recommended). The measure is already proven on the scenario by
    `Traffic_link_check`.
  - **Code:**
    - `finance.py`: dataset `traffic_link` (`finance.kpi_traffic_link`, test twin) with `LINK_NOTE` ("moves with,
      never a cause").
    - `weekly_pack.py`: `link_evidence()` adds `context.link` in the kpi node (NileGate data, level 2; the
      `context.` id puts it on slide 9), plus a digest row and one Insight prompt clause.
    - `render.py`: slide 9's code-drawn link line (`link_line()`): a fixed label, r lag 0 / lag 1 / threshold as
      bound values, a fixed verdict ("Moves with traffic (not a cause)" / "No measurable link"), and before week 13
      a fixed "too few weeks" sentence.
  - **Offline on W16's real draft:** the link line on weeks 16 / 30 / 8 gives V8 read-back 0 problems, and the
    Validator passes.
  - **Checks:** `Deck_check` 8 / 8; `Tools_check` 8 / 8 (+ `ORDER_KEY["traffic_link"]`; the tool's columns = the
    views, rows = the view on 52 weeks); `Finance_qa_check` 5 / 5; `Supervisor_check` 9 / 9 (its reviewed largest
    request 7,339 → 7,402 est. tokens from the longer tool schema; still fits); lint ratchet clean.
    `Weekly_pack_check` (+ `context.link` in its evidence keys and direct evidence) is running.
  - The API's finance route keeps its own dataset list, so the OpenAPI is unchanged.
- 2026-11-09 — **Phase 5 done.**
  - **V10** (`validator.link_problems`) and the `models.Problem` rule V10. See ADR-051 amendment 8.
  - **Skill lines approved by the owner** ("موافق، شغّل التقييم"): weekly-variance-analysis (the "correlation is not
    cause" rule), deck-style-guide (slide 9 row) and finance-qa (the `traffic_link` dataset).
    - **D-TL-9:** the three bodies then exceeded the loader's 1,200-token cap (1,234 / 1,319 / within). They were
      shortened keeping the approved meaning: the step-7 sentence on `context.link` was dropped and the rule reads
      "Say billing "moved with" them only in one summary bullet citing `context.link` when its `link` is `link`;
      never "because of", "due to" (V10)". "driven by" is no longer named in the skill, but V10 still refuses it.
    - Now 1,185 / 1,197 / 1,188 tokens; `reviewed_by_owner: 2026-11-09`.
  - **Fixes the checks asked for:**
    - `run.json` `external_context` excludes `context.link` and gains `traffic_link` (External_context_check).
    - finance-qa writes no_link without backticks (Tools_check refuses an unknown backticked name).
    - `Supervisor_check`'s reviewed date for finance-qa is now 2026-11-09.
    - `Deck_check`'s reviewed snapshot now records V10 on the two "external cause" classes.
  - **Checks:** `Traffic_link_check` 6 / 6 (+ Phase 5: V10 8 / 8 planted, 0 clean refused); `Deck_check` 8 / 8;
    `Tools_check` 8 / 8; `Finance_qa_check` 5 / 5; `Supervisor_check` 9 / 9; `External_context_check` and
    `Approver_request_check` pass; lint clean; `Weekly_pack_check` 9 / 10 after every Phase 4–5 change (Phase 5 =
    real models, on request).
  - **Next: Phase 6.** Acceptance per L5 + D-TL-7: golden weeks × 2 (packs) and the full Q&A (EN + AR) × 2, then one
    live pack and the plan's close.
- 2026-11-11 — stabilization R5/R6 repaired the shared claim enforcement before Phase 6. `traffic_claims.py` now
  checks deck text, both Q&A paths, human analysis edits and model notes with cited M17 view provenance, verdict
  agreement and the invoice-count metric scope. Fixed EN/AR wording is available to the tool. The original 8 V10
  planted cases remain; the new pinned 66-case suite passes on every surface, including negation and Arabic.
  Unsafe notes stop before the Writer (or restore a failed revise). SQL and accepted statistical thresholds are
  unchanged. This conservative deterministic guard needs false-refusal and paraphrase measurement in Phase 6;
  no real-model acceptance was run. PortPilot is the current product name (ADR-068); original evaluations remain.
- 2026-11-12 — owner full database audit reviewed (`db/audit/2026-11-12_stabilization_report.txt`). Sections
  26–28 match the reviewed PortWatch/scenario/M17 values and permissions, and all finance view columns have
  comments. Schema snapshot refresh remains pending. The separate 15 missing statistics activity timestamps
  are under read-only investigation in the stabilization plan; no traffic/model acceptance is claimed by this audit.
- 2026-11-12 — schema export reviewed and promoted through 028. The three M17 views and all 56 added comments
  match the expected 027/028 additions; no existing definitions changed. The full audit and snapshot follow-up
  are complete (`db/audit/2026-11-12_schema_review.md`). Planner statistics are present on all 15 project tables;
  the missing activity timestamps did not establish a missing-statistics defect. Next deterministic acceptance:
  owner finance/reference check, then traffic/reference check. Phase 6 real-model acceptance remains open.
- 2026-11-12 — **Phase 6 started** (owner: "ابدأ Traffic Phase 6"). Two blockers found before any model call:
  - `Traffic_link_check.py` (and `Suez_transits_loader.py`, `Finance_scenario_generator.py`) had no project-root
    `sys.path` line, so `tools/run.py` failed with `ModuleNotFoundError`. Line added; `Traffic_link_check` 6 / 6.
  - **D-TL-10 (owner's choice, asked as clickable options):** `Stage1_eval.py` Phase 3 (fake models, 0 calls)
    failed `deck_numbers_100` at 0.6364 — the four `finance_test` weeks. Cause: the 2026-11-11 rename changed the
    audit tool's note to "not PortPilot's invoices" while the frozen `golden_weeks_expected.json` holds
    "not NileGate's invoices". Chosen fix: `holds_frozen` reads the two product names as equal in text values;
    every other character and every number still must match. Frozen files, their hashes and the baselines are
    unchanged. After it: Phases 1–4 pass (6 validation lines, 0 calls, 0 artifacts changed).
  - Acceptance runs: packs scope, 2 repeats, tag `tl1`, compared with `stage1_eval_2026-11-08_ec2.json`; then the
    Q&A scope, 2 repeats, tag `tl1qa`, compared with `stage1_eval_2026-10-31_dp127b.json`; then one live pack.
- 2026-11-12 — **Phase 6 packs run `tl1`: INCOMPLETE, and repeat 1 is a reject. Acceptance NOT met.**
  - Run: packs scope, real models, 5,863 s. Repeat 1 complete (11 weeks); repeat 2 stopped after 4 weeks — Gemini
    flash-lite answered 503 UNAVAILABLE for most calls and the OpenRouter fallback reached its 50 requests / day.
    Usage of the day: Gemini 11, OpenRouter 50. Repeat 1: 66 calls, 32 of them fallbacks — this run measured
    mostly the fallback model, not the primary. No results file was written (partial:
    `Notebooks/_scratch/stage1_eval/stage1_eval_partial.json`; caches `llm_cache/eval_tl1_r1|r2/`).
  - Repeat 1: **4 / 11 published**, planted **0 / 6**, narrative recall **0.4483** (ec2: 11 / 11, 6 / 6, 0.9483);
    deck numbers, false alarms, claims, traceability held on the 4 published packs. The 7 others ended
    `output_invalid` at `insight_notes V10` — the stabilization slice-3 stop before the Writer (R5/R6).
  - Cause, read from the cached notes (33 note objects): the models mostly wrote **true denials**, and the shared
    regex policy `traffic_claims.classify` refused them. Seen: "billing did not move with Suez transits; a link is
    never a cause" → `causal`; "correlation is not cause" → `causal`; "no Suez billing link is claimed" and "billing
    is not claimed to move with Suez transits" → `association`; "has no statistical link to" → `association`; "not
    measurable yet (NULL before week 13)" → `association`. `note_problems` also checks `caveats` with no evidence
    ids, so any caveat that mentions the link — correct or not — fails "cite one unambiguous traffic_link result".
    One sentence was a true catch ("Billing moved with Suez transits according to the weekly traffic link analysis").
  - Design weakness: a single refused sentence in the notes stops the whole pack (no repair, no rewrite), where
    before slice 3 the deck Validator's V10 patch-rewrote the one bullet. A wording slip now costs the week's pack.
  - Not run: the Q&A scope (`tl1qa`) and the live pack — held until the guard is decided, so no quota is spent on
    a candidate that will change. Owner decision pending (repair in code / revert the notes-stage stop / re-run only).
- 2026-11-12 — **D-TL-11 (owner: "تمام كمل" on the recommended option "fix the check in code"): the notes-stage claim
  guard repaired; a refused sentence no longer stops the pack.** Scope: `pipelines/agents/traffic_claims.py`,
  the `insight_notes` node of `weekly_pack.py`, `Traffic_claims_check.py` + a second pinned fixture.
  - **Classifier (false refusals read from the tl1 notes):** `NEGATIVE` accepts the denial forms the real models
    wrote — "no statistical / measured / Suez billing link" (a fixed list of qualifiers, so "no doubt the link …" is
    never a denial), "did not show a measured link", "is not claimed to move with", "cannot be said to have moved";
    `INSUFFICIENT` accepts "not measurable yet" and "link is null"; a threshold week ("null before week 13") is no
    longer read as the week the claim is about; in a "…, but …" sentence only a clause that states a relation
    inherits both domains, so "transits averaged 35.6, but the invoice count shows no measurable link" is the
    independent fact + the denial it is. the 66 pinned pinned cases are unchanged and still pass on every surface.
  - **Caveats** (plain strings, no evidence ids) are judged against the run's own M17 results, found by
    provenance (`traffic_ids`: tool `finance_kpi`, status ok, a `kpi_traffic_link` view) — before, every caveat
    that mentioned the link failed "cite one result", correct or not.
  - **Repair instead of stop (`repair_notes`):** a refused sentence in the notes is removed and the fixed M17
    wording of the run's own verdict is put in its place (code, no model call; the M17 evidence id is added; a
    caveat is replaced whole). Each repair is one line in the state's `normalized` list (saved in `run.json`,
    counted as `form_fixes` by the API). With no single measured verdict in the run nothing is repaired and the
    run stops `output_invalid` exactly as before; the revise path still restores the reviewable pack. The deck
    Validator's V10 and both Q&A checks are untouched: they remain the final gate.
  - **Proof (0 model calls):** new fixture `fixtures/traffic_claims_real.json` — 53 sentences the real models wrote
    in tl1, labels reviewed by hand (50 sound, 3 unsafe), SHA-256 pinned; `Traffic_claims_check.py` 5 phases
    (+ Phase 5: the real sentences, the repair on EN/AR notes, all 119 pinned cases end as safe notes). Replay of
    the 37 cached real note sets with each week's real `context.link`: before the fix 7 of repeat 1's 11 packs
    stopped; now 34 pass as written, 3 are repaired (a "moved with" claim and two "no link" claims on weeks whose
    verdict is "too few weeks"), **0 stop**.
  - **Limit, stated:** this is still a bounded regex guard. A new paraphrase can be refused again; the difference
    is its cost — one sentence replaced by fixed wording, not the week's pack.
  - **Checks after D-TL-11 (fake models, 0 calls):** lint ratchet ruff 0 / pyright 0; `Traffic_claims_check` 5 phases;
    `Deck_check` 8 / 8; `Weekly_pack_check` 9 / 10 (Phase 5 = real models, on request); `Approval_safety_check`,
    `Publication_check`, `External_context_check`, `Approver_request_check` pass; `Stage1_eval` Phases 1–4.
    Two reviewed snapshots were stale since the 2026-11-11 rename (not caused by D-TL-11) and were corrected:
    `Finance_qa_check` compared the first 22 characters of "PortPilot billed 8.39 M" (23 long; 22 fitted the old
    name) → 6 / 6; `Supervisor_check`'s largest request 7,402 → 7,404 est. tokens (still fits) → 9 / 9.
  - Gemini probe 2026-11-12 21:30 UTC: 4 / 4 tiny calls answered (the 503 spell is over); OpenRouter stays
    exhausted until 00:00 UTC. **Packs run started again on fresh caches, tag `tl2`** (the candidate changed, so
    tl1's caches — mostly fallback-model notes — are not reused), compared with `stage1_eval_2026-11-08_ec2.json`.
- 2026-11-12 21:32 UTC — **`tl2` first attempt: INCOMPLETE after 2 packs** (185 s). Both — test:10 and test:23,
  two of the weeks tl1 lost to the notes guard — were **published, planted 2 / 2 each, findings 2 / 2, 0 false
  alarms**. The third pack stopped: Gemini answered 503 again and the OpenRouter fallback stays exhausted until
  00:00 UTC, so no model was available. No results file yet; caches in `llm_cache/eval_tl2_r1/`.
  - **Risk noticed in `llm.py` (existing rule, not changed):** a request that fails with a 5xx in
    `REPEATED_SERVER_RUNS = 2` separate runs is cached as a deterministic failure ("a property of the request, not
    an outage"). During an outage that lasts hours, re-running turns outage failures into cached failed items.
    Five Gemini requests stand at 1 run today; none is cached as failed. So the run is **not** retried blindly.
  - **Guarded resume (unattended, started 21:35 UTC):** waits for 00:06 UTC (the fallback's day resets), then
    a Gemini probe (6 tiny public prompts, all must answer) before each attempt; packs `tl2` vs ec2, then the Q&A
    scope `tl2qa` vs `stage1_eval_2026-10-31_dp127b.json`; at most 4 attempts per scope, 25 minutes apart, each
    resuming from the caches. Runner and logs: the session scratchpad (not project files).
- 2026-11-13 07:55 UTC — the guarded resume of the night **never ran**: the machine went down while the runner was
  waiting (the three database containers show a fresh start; `project-web-1` and the retained `portpilot-api-test`
  exited 255), so no attempt, no model call and no cache change happened overnight. Gemini probe now 6 / 6;
  OpenRouter's new day has 50 requests. `tl2` packs run resumed directly (attended), from the caches of the two
  packs already published.
- 2026-11-13 08:45 UTC — **`tl2` packs run COMPLETE: `stage1_eval_2026-11-13_tl2.json`.** Scored verdict vs ec2:
  **"reject" on two gates — both scored sentences are true by hand** (owner decision pending, as in D-C4-1 / c5b).

  | | ec2 (baseline) | tl2 repeat 1 | tl2 repeat 2 |
  |---|---|---|---|
  | packs published | 11 / 11 | 11 / 11 | 11 / 11 |
  | deck numbers | 100 % | 100 % | 100 % |
  | planted found | 6 / 6 | 6 / 6 | 6 / 6 |
  | traceability | 100 % | 100 % | 100 % |
  | claim accuracy | 100 % | **0.8889** (1 of 9) | 100 % |
  | false-alarm rate | ≤ 5 % | 0 | **0.10** (1 of 10) |
  | narrative recall | 0.9483 (mean) | 1.0 | 0.9655 → mean **0.9828** (+0.0345) |

  - No pack stopped at the notes guard (tl1: 7 of 11). Calls: repeat 1 55 (0 fallbacks); repeat 2 87, of which
    30 fallbacks and 32 failed calls — Gemini answered 503 again from 08:20 UTC and the last packs ran on the
    OpenRouter fallback (≈ 7 minutes a pack).
  - **Scored wrong claim (repeat 1, live:48), true by hand:** "Budget variance was {budget_variance_pct} above
    budget this week, but {budget_variance_13w_pct} below budget over the 13-week period" — the view gives
    +18.82 % and −15.62 %. The scorer `claims` reads the 40 characters *before* each slot: the second slot's
    window holds "above" (which belongs to the first slot) and not its own "below" (which follows it), so a
    negative value "after an up word" is counted wrong.
  - **Scored false alarm (repeat 2, live:15), true by hand:** "The week's finding is a duplicate of INV-0000491;
    the action is to void the duplicate …" — the audit flags INV-0000925 as a duplicate of INV-0000491. The
    scorer `false_alarms` exempts an original only when the flagged invoice is named in the same sentence or the
    word "original" is used; "a duplicate of <original>" alone is not covered. Same family as the c4 case
    (live week 15, "matched original invoice INV-0000491").
  - Neither sentence comes from the D-TL-11 repair or from a traffic claim. The traffic part of the acceptance
    (no pack lost to V10, no unsafe traffic sentence published) held in all 22 packs.
  - **Q&A scope started** (tag `tl2qa`, 2 repeats, vs `stage1_eval_2026-10-31_dp127b.json`) after a Gemini probe 6 / 6.
- 2026-11-13 — **D-TL-12 (owner: "وسّع قواعد المُقيِّم"): two scorer rules widened, `tl2` scored again from its
  caches → ADR-052 "keep (better)" vs ec2.**
  - `claims`: a direction word counts for the value of its own clause — the 40 characters before a slot are cut
    at the last `,` `;` or contrast word (but / while / whereas / yet / however, لكن / بينما). Phase 2 cases:
    `direction_other_clause` 0 (the tl2 sentence), `direction_own_clause` 1 ("…, and rose {negative}" is still
    wrong), `wrong_direction` 1 unchanged.
  - `false_alarms`: "a duplicate / copy of INV-X" names X as the original, only when X is the original of one of
    the week's flagged invoices. Phase 2 cases: `duplicate_of_original` 0 (the tl2 sentence), `duplicate_of_other`
    1 (a non-original is still an alarm), `original_called_duplicate` 1 unchanged.
  - **Replay mode `EVAL_REPLAY=1`** (new, `Stage1_eval.py` only): a finished run is scored again from its caches;
    a request that is not cached is refused before the network, so the role takes the next candidate exactly as it
    did when the main model was down; a request in no cache stops the replay. `llm.py` / `roles.py` untouched.
    Results go to `…_<tag>_rescored.json`; the original results file is never overwritten.
  - **`stage1_eval_2026-11-13_tl2_rescored.json`:** 22 / 22 packs, **0 fresh calls** (142 recorded calls read
    from the caches). Field by field against the original file, only three values differ: live:48 repeat 1
    `claims` 3 → 2 and `claims_wrong` 1 → 0; live:15 repeat 2 `false_alarms` 1 → 0. Every other metric of every
    pack is identical. Gates: all five hold in both runs; narrative recall 0.9828 vs 0.9483 (+0.0345) →
    **ADR-052: no gate regressed, verdict "keep (better)"**. ec2 itself held both gates under the old rules, and
    the two rules only remove flags of these two forms, so the baseline's side of the comparison is unchanged.
  - Lint ratchet 0 / 0. The Q&A scope (`tl2qa`) is still running; the live pack is not done.
- 2026-11-13 — **Q&A scope `tl2qa` COMPLETE: `stage1_eval_2026-11-13_tl2qa.json` — ADR-052 "reject" vs dp127b.**
  42 questions × 2, real models, **0 fallbacks, 0 failed calls** (86 / 87 calls a run). Hard gates all hold in
  both runs: traceability 100 %, RBAC leakage 0, abstention recall 100 %, numbers 100 %. Arabic completeness
  **1.0** (= baseline). English completeness **0.913** vs 1.0 (−0.087, more than the 0.03 allowed): the same two
  questions fail in both runs. Neither is a traffic question (the golden set v2 was frozen before M17).
  - **q01** "How much did NileGate bill in week 23 of 2025?" → `not_in_data`: "NileGate did not bill any amount in
    week 23 of 2025, or is not among the top-10 customers". Since the 2026-11-11 rename every brief and skill says
    PortPilot and nothing tells the model the company's earlier name, so it reads "NileGate" as a customer.
    Baseline answer: "NileGate billed 8.39 M SDR in week 23 of 2025 across 29 invoices". **A real effect of the
    rename on users** (older decks and reports carry the old name), not only on the frozen question. a01 / a02
    (abstention questions with the old name) still abstain correctly.
  - **r04** (the Port of Rotterdam annual-report revenue, a document question) → `validation_failed`, "numbers
    typed as text": run 1 `['82']` (the answer ends "pages 12 and 82"), run 2 `['894461000', '940355000', '82']`
    (the model expanded "894,461 (in thousands)" to full figures). The baseline answer quoted the two figures and
    gave no page list. The checker's refusal of a figure that is not in the document's own text is right; whether
    page 82 is in the tool's text for this retrieval is **not yet inspected**.
  - r03 / r03b / r05 answer `not_in_data` where `not_permitted` is expected — as in the baseline; `refusal_ok`
    holds and no restricted figure is shown.
  - Since the last full Q&A run (c5qa, 2026-11-03, a tie with dp127b) the tree gained the API memory, the
    approver work, external context, the `traffic_link` dataset, the shared claim guard and the rename; this run
    is the first Q&A measurement of all of them together. The cause of r04 among them is **uncertain**.
  - **Phase 6 status:** packs — met (`tl2_rescored`, keep (better)); Q&A — **not met**; live pack — not run.
    Owner decision pending on q01 (an alias for the old name in the two Q&A briefs) before a second Q&A run.
- 2026-11-13 — **D-TL-13 (owner: "أيوه، ضيف وأعد"): the company's former name in the two Q&A briefs; the citation
  page rule repaired; Q&A run again as `tl3qa`.**
  - `finance_qa.FORMER_NAME` — one sentence ("PortPilot was called NileGate until November 2026: a question that
    says NileGate means the company itself, never a customer; answer with the name PortPilot") — is added to
    `QA_TASK` and to the supervisor's `SUP_TASK` (code briefs; no reviewed skill changed).
  - r04 inspected: `search_documents` returns the page as a number field (`citation.page = 82`), and the checker's
    exemption for "a citation's page" (D-P7-15) collected string values only, so "pages 12 and 82" was refused
    (12 passed only as a small integer). `check_answer` now also allows the cited rows' `citation.page`. A figure
    that is in no passage (run 2's "894461000") is still refused. Self-test added in `Stage1_eval.py` after the
    D-P7-15 case (page named → no problem; expanded figure → one problem).
  - Checks (fake models): lint 0 / 0; `Finance_qa_check` 6 / 6; `Memory_check` 4 / 4; `Traffic_claims_check` 5
    phases; `Supervisor_check` 9 / 9 after its reviewed largest request moved 7,404 → 7,457 est. tokens (the new
    sentence; still fits).
  - **Open, stated:** the supervisor's brief changed, and the Stage 2 golden set (57 items) has not been run on
    it — `Stage2_eval` no-regression is owed before this is called closed for the supervisor.
  - `tl3qa` started after a Gemini probe 6 / 6 (the day's usage before it: Gemini 229 of ≈ 500, OpenRouter 31).
- 2026-11-13 15:37 UTC — **Q&A scope `tl3qa` COMPLETE: `stage1_eval_2026-11-13_tl3qa.json` — ADR-052 "tie: keep"
  vs dp127b.** 42 questions × 2, real models, 0 fallbacks, 0 failed calls (86 / 83 calls). English completeness
  **1.0**, Arabic **1.0** (both = baseline); traceability 100 %, RBAC leakage 0, abstention recall 100 %, numbers
  100 %, G2 holds. q01 (the former name) and r04 (the Rotterdam report, page named) are answered in both runs.
  r03 / r03b / r05 answer `not_in_data` where `not_permitted` is expected, as in the baseline (`refusal_ok` holds).
- **Phase 6 acceptance, as measured on the tree of 2026-11-13:**

  | Part (L5 + D-TL-7) | Result | File |
  |---|---|---|
  | Golden weeks × 2 (packs) | **met** — keep (better): all five gates in both runs, narrative recall 0.9828 vs 0.9483 | `stage1_eval_2026-11-13_tl2.json` (as run) + `…_tl2_rescored.json` (D-TL-12 scorer) |
  | Full Q&A EN + AR × 2 | **met** — tie: EN / AR 1.0, all gates | `stage1_eval_2026-11-13_tl3qa.json` (`…_tl2qa.json` = the rejected run before D-TL-13) |
  | One live pack | **not run** — the owner's step (a real week, approved through the UI or the CLI) | — |

  The packs run predates D-TL-13; that change touches the two Q&A briefs and `finance_qa.check_answer` only, which
  the pack graph does not use, and the D-TL-12 scorer was applied to the packs by the replay.
- **Still owed before the plan closes:** the live pack; `Stage2_eval` no-regression for the supervisor (its brief
  gained the former-name sentence, and it has not been measured since `traffic_link` and the shared claim guard
  were added) — about 340 calls, the next Gemini day; then the implementation record, ADR-051 amendment(s) for
  D-TL-11 / 12 / 13, `ARCHITECTURE.md`, ROADMAP and the archive.
- 2026-11-13 — preparing the owed `Stage2_eval`: its fake-model Phase 3 failed on the route thread guard of the
  stabilization slice 2 (same route asked twice on an in-memory saver). Fixed in `tools/products.py` (the next
  free thread number instead of an error; recorded in the stabilization plan). `Stage2_eval` Phases 1–3 pass.
  The real run (57 items × 2, ≈ 340 calls) waits for the next Gemini day: 385+ of ≈ 500 requests are used today.
- 2026-11-13 15:50 UTC — owner: the Git checkpoint comes **after Stage 2**. A guarded runner waits for the next
  Gemini day (2026-11-14 08:10 UTC), probes the model (6 / 6 required), then runs `Stage2_eval` real, 2 repeats,
  tag `tl3s2`, compared with `stage2_eval_2026-10-30_c1.json`; at most 3 attempts, 25 minutes apart. It runs
  only while the machine stays on (the runner of 2026-11-12 died with the machine); otherwise it is started by
  hand: `$env:EVAL_REAL_MODELS='1'; $env:EVAL_REPEATS='2'; $env:EVAL_TAG='tl3s2';
  $env:EVAL_BASELINE='stage2_eval_2026-10-30_c1.json'; uv run python tools/run.py pipelines/scripts/agents/Stage2_eval.py`.
- 2026-11-14 08:12 UTC — the overnight runner died with the machine again (no attempt, no call). Gemini's new day:
  probe 6 / 6. `Stage2_eval` real run started attended: 2 repeats, tag `tl3s2`, vs `stage2_eval_2026-10-30_c1.json`.
- 2026-11-14 08:50 UTC — **`Stage2_eval` COMPLETE: `stage2_eval_2026-11-14_tl3s2.json`.** 57 items × 2, real
  models, **0 fallbacks, 0 failed calls** (165 / 168 calls). **Done-when: MET** — every hard gate holds in both
  runs (RBAC leakage 0, twins 100 %, abstention 100 %, numbers 100 %, traceability 100 %), completeness EN ≥ 0.85,
  AR ≥ EN − 0.10. **ADR-052 vs c1: "reject"** — completeness EN **0.8861** vs 0.9816 (−0.0955), AR **0.9125** vs
  0.95 (−0.0375); no gate regressed.
  - Every miss is an operations / route item (o01, o06, o08, o11, o12, o09_ar, c07 and twins). None is a finance
    traffic question or uses the former name.
  - **6 of the 14 misses are slot-form slips the model repeats after its one patch → `validation_failed`:**
    the format written with its kind (`|money sdr`, `|money_sdr` — the brief says "Formats: money M / k / sdr"),
    and a slot on a text field (`{…:as_of}`, `{…:next_port}`: "is not a number: copy it as text"). The numbers
    behind them are right; `slots.normalize_text` (D-P7-14) does not cover these two forms. Counted as answered
    in full, completeness would be EN 0.9773 / 0.9602 and AR 0.925 / 1.0 → means **0.969 / 0.9625**, inside
    ADR-052's 0.03 of c1 (an upper bound, not a measurement).
  - The other 8 are answers that leave out one asked element (o06: the destination's name; o01: the speed;
    c07: one part) — the kind c1 itself has (its run 2: o01 0.5, c07 0.75, o01_fe 0.5).
  - Cause: **uncertain**. The same slot-form family stopped the c5 Stage 2 run on 2026-11-03 (D-RR-1, closed on
    a hand-check), before the rename and the former-name sentence; the model's behaviour on these briefs is the
    likelier cause than this session's changes, but there is no same-day run without them to prove it.
  - Owner decision pending: extend the slot-form normalizer and score again from the caches, or close on the
    done-when with c1 kept as the baseline.
- 2026-11-14 — **D-TL-14 (owner: "وسّع مُصحِّح الـ slots"): two slot-form rules for the supervisor's answers;
  the three recorded evaluations replayed on the final tree.**
  - `slots.normalize_text(…, answer_forms=True)`: the format written with its kind (`|money sdr`, `|money_sdr`) →
    the format alone; a slot on a text field (`{…:next_port}`, `{…:as_of}`) → the field's own text. The number is
    never touched; each fix is listed in the run record as before. `Supervisor_check` gains 4 cases (two kind
    forms fixed, an unknown kind word left for the checker, a text field copied) and one proving the default is
    unchanged.
  - **Scope narrowed by a measurement:** applied to every caller of `normalize_text`, the two rules made the pack
    replay (`tl2`, first pack, a Writer patch) and the Q&A replay (`tl3qa`, q21 run 2) stop on a request that is in
    no cache — a draft fixed differently is followed by a different patch request. So the rules are on only where
    they were measured, the supervisor (`supervisor.py`); the pack Writer, the finance Q&A graph, route advice
    and the voyage watch keep D-P7-14's set and would each need their own run to adopt them.
  - `EVAL_REPLAY=1` added to `Stage2_eval.py` (same `ReplayQuota` as Stage 1).
  - **Replays on the final tree — 0 fresh calls in all three:**

    | Evaluation | File (2026-11-14) | Result |
    |---|---|---|
    | Packs `tl2` vs ec2 | `stage1_eval_2026-11-14_tl2_rescored.json` | keep (better); identical item by item to the 2026-11-13 re-score |
    | Q&A `tl3qa` vs dp127b | `stage1_eval_2026-11-14_tl3qa_rescored.json` | tie; identical item by item to the run |
    | Stage 2 `tl3s2` vs c1 | `stage2_eval_2026-11-14_tl3s2_rescored.json` | done-when MET; EN 0.9448 (−0.0368), AR 0.9625 (+0.0125) → **"reject" by 0.0068** |

  - Stage 2 detail: the six slot-form items are recovered (o11 ×2, o12, o09_ar → 1.0; o01, o01_fe run 1 →
    answered at 0.5), 300 recorded calls read from the caches (fewer than the run's 333: no patch call is needed
    any more). What remains is the model leaving out one asked element, with the value present in the tool row:
    o01 and its twins say where the vessel is but not that it is in transit; o06 says "its destination" and not
    DOCAU (the row holds `destination: DOCAU`); o08 run 1 and c07 run 2 miss one value. c1's own run 2 had three
    such misses. These are answer-wording misses a form fix cannot reach; closing the last 0.007 needs a brief or
    skill change and a new real run. Owner decision pending.
  - Checks: lint 0 / 0; `Supervisor_check` 9 / 9, `Deck_check` 8 / 8, `Finance_qa_check` 6 / 6,
    `Route_advice_check`, `Voyage_watch_check` pass.
- 2026-11-14 — **D-TL-15 (owner: "اقفل وروح للـ commit"): Stage 2 closed on its done-when; c1 stays the Stage 2
  baseline.** `stage2_eval_2026-11-14_tl3s2_rescored.json` is a record, not a baseline: every hard gate holds in
  both runs and completeness EN 0.9448 ≥ 0.85, AR 0.9625 ≥ EN − 0.10; against c1 it is −0.0368 EN (ADR-052's
  limit 0.03) from answers that leave out one asked element — recorded as the model's answer wording, as on
  2026-11-03 (D-RR-1). No brief or skill is changed for it.
- **Phase 6 state at the Git checkpoint:** packs — met (`tl2`, keep (better)); Q&A — met (`tl3qa`, tie); the
  supervisor's no-regression — closed on the done-when (D-TL-15). **Still open:** the one live pack (the owner's
  step), then the implementation record, the ADRs (ADR-051 amendment for D-TL-11 / 12, ADR-052 use, ADR-059 /
  ADR-068 notes for D-TL-13 / 14), `ARCHITECTURE.md`, ROADMAP and the archive. The plan stays in `docs/plans/`.
- 2026-11-14 09:40 UTC — **the live pack, week 16, on the committed tree (`423b7bd`).**
  - **Before it (read-only):** `W16:1` and `W16:2` ended `output_invalid`; `W16:3` and `W16:4` waited for a decision,
    both DEGRADED, both titled "NileGate" and produced before D-TL-11 … D-TL-14 (W16:3's slide 9 said "External
    context unavailable"). **Owner's choice (clickable options): reject both and start a new attempt.** Rejected as
    employee 6 at 09:41 UTC with the comment "Stale attempt: produced before D-TL-11..D-TL-14 and the PortPilot
    rename …" (versions `6e682ec4aa7d5725`, `5df4275b3b245f26`).
  - **Model state before the run:** usage of the day Gemini 317 of ≈ 500, OpenRouter 0 of 50; Gemini probe 6 / 6.
  - **`weekly_pack:live:2025-W16:5`** (`run --week 16 --as 6`): `awaiting_approval`, Validator **passed, 0
    problems**, review version `6bfe8cc71ea849a4`, preview
    `reports/_drafts/weekly_pack_live_2025-W16_5_6914c3480a.pptx` (10 slides, title "PortPilot Weekly Finance Pack").
  - **Calls:** 5 answered — 3 on Gemini flash-lite (insight, notes, the Writer's draft), **2 on the OpenRouter
    fallback** (both Writer patch rewrites: Gemini answered 503 on the first rewrite and was stopped for the run;
    257 s and 81 s). So the draft is the primary model's; the two rewrites are the fallback model's.
  - **DEGRADED** (`draft_origin: fallback`): 4 checks still failed after the two rewrites, so code dropped three
    bullets and replaced none — the DSO bullet on slide 6 (V7 + V9: tiles repeated, `dso_delinquency_days` not
    named), the audit-week bullet on slide 8 (V9: tiles repeated) and a third bullet on slide 9 (see below).
    23 bullets remain; no slide and no title was written by code.
  - **The traffic link, as the plan designs it (§3e):**
    - Evidence `context.link` (view `finance.kpi_traffic_link`, week 16): `link = no_link`, r same week −0.067,
      week before −0.114, threshold 0.5, n = 16 weeks.
    - Notes: `context[1]` is the fixed M17 wording as the model wrote it ("No measurable link was found between
      the weekly invoice count and Suez transits over the observed weeks."). **The D-TL-11 notes repair did not
      fire** — no `insight_notes V10` line; the 7 `normalized` lines are all D-P7-14 slot-form fixes (`|dir`, `days`).
    - Slide 9, read back from the preview PPTX: title "Suez transits average 35.6 per day with no measurable link
      to weekly billing"; the code-drawn line "PortPilot billing vs Suez transits so far this year — r: same week ·
      week before · threshold" −0.067 / −0.114 / 0.5 → **"No measurable link"**; footer "External context: public
      data and news, not PortPilot figures". No causal word on any slide's bullets.
    - The Writer also put the same sentence as a *bullet* on slide 9 citing `context.link`; **V5 refused it**
      ("slide 9 is external context only: no PortPilot figure or result here") in every round, the rewrites
      replaced it with a transit total on a field that does not exist (V2), and the fallback dropped it. The
      verdict is still on the slide through the code-drawn line and the title. **Observed, not changed:** the
      notes give the Writer a sentence that V5 forbids as a slide-9 bullet, which costs rewrites — a brief /
      skill question for a later plan.
  - **Decision (the owner, through the web UI): APPROVED** as employee 6 (manager / Finance) at 2026-11-14
    09:59:12 UTC, no comment, no edit (23 bullets as drafted). Thread status `published`, next END.
  - **Publication verified (read from disk):** `reports/2025-W16/_publications/9f145f3119d44e6a903736a7c6913ba7/`
    holds the four files (`approval.json`, `deck.pptx`, `deck_draft.json`, `run.json`); their SHA-256, computed
    again, equal the four hashes in `reports/2025-W16/publication.json` (version 1, thread `…W16:5`).
    `run.json`: `traffic_link` = the week-16 M17 row (`no_link`, r −0.067 / −0.114, threshold 0.5, n 16);
    `external_context` = `context.suez` ok (IMF PortWatch) and `context.news` ok, without `context.link`
    (as D-TL Phase 5 fixed it); `degraded` and the 7 `normalized` lines are kept. **Database sync: `synced`**,
    1 attempt, 09:59:13 UTC — no reconcile needed.
  - **Not verified:** the published `deck.pptx` was not opened slide by slide (the preview of the same draft
    was); the Power BI "Approved Pack" page was not opened; the web UI screens were not inspected .
  - **Phase 6 acceptance: all three parts met** (packs `tl2`, Q&A `tl3qa`, the live pack `W16:5`). Left: the
    implementation record, the ADRs, `ARCHITECTURE.md`, ROADMAP and the archive (owner: archive without
    another stop).
- 2026-11-14 — **plan closed.** Implementation record at the top; ADR-051 amendment 11, ADR-052 seventh use,
  notes on ADR-059 and ADR-068; `ARCHITECTURE.md`, `docs/ROADMAP.md` and the project rules' current-phase line
  updated; the file moved to `docs/archive/2026-11-14_Traffic_billing_link_plan.md` with a row in
  `docs/archive/README.md`. The commit is the owner's.
