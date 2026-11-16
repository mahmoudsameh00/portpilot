# Plan — model flexibility: any model, from any provider, changed in one reviewed file

**Status: IMPLEMENTED (2026-11-15)** — implementation record (the plan below is kept as approved):
- **Done:** Phases 1–5. `pipelines/agents/models.toml` + `model_config.py`; `llm.py` / `roles.py` read them (adapters
  `gemini` / `groq` / `openai_compatible` / `langchain`; per-model limits, temperature, timeout, method, price + daily
  cap); `EVAL_MODELS` for `Stage1_eval` / `Stage2_eval` / `Weekly_pack_check` (and `Model_probe`); the outage-aware
  repeated-failure rule (M7); `cost_usd` per call + `spend.json` (M5); `fallback_share` in the pack's `run.json`, the
  API's pack view (shown in Reports) and the evaluations (W10); `Model_probe.py`; `docs/model_swap.md`.
- **Proof:** `Models_config_check.py` 3 / 3 (48 cache keys byte-equal to the pre-file payload); every fake-model check
  unchanged (10 scripts); probe of the four models, every line passes; no-regression **without spending quota** —
  cache-only replays of s9 (packs) and tl3qa (Q&A): 0 fresh calls, primaries identical, ADR-052 "tie"; Stage 2 on
  tl3s2's caches: 0 fresh calls in 300 requests, primaries identical to `stage2_eval_2026-11-14_tl3s2_rescored.json`.
- **Deviations:** the loader is `model_config.py` (no import cycle with `roles.py`); the probe's size line is capped
  at 75 % of a model's per-minute token limit; Phase 5 = replays / cache runs instead of two fresh provider days (the
  models did not change, and an identical cached request is the strongest proof of it); model-naming comments left.
- **Open note:** the Stage 2 cache-only replay stopped at item a03 (one request refused as "not in the cache") while
  the non-replay run on the same caches minutes later served that request from the cache — not caused by a key
  change; the replay path's handling of that item (it calls PortWatch for a not-yet-settled window) is unexplained.
- **ADR:** ADR-045 amendment 4. Owner: one commit (commands in the session's closing message).

**Status: APPROVED (2026-11-13, owner: "موافق", with the recommended answers to M4–M7)** — written PROPOSED the same day, on the owner's request ("we want things flexible, so that if one day we
change the main model or the fallback to a stronger real model, nothing falls over"). Owner decisions asked as
clickable choices the same day: **M1** a configuration file in the project, **M2** "any model from anywhere",
**M3** the plan now, the implementation after traffic Phase 6 closes. No code before the owner approves this plan.

**Order:** it touches `pipelines/agents/llm.py` and `pipelines/agents/roles.py`, the two files every ADR-052
evaluation runs on. It therefore starts only after `Traffic_billing_link_plan.md` Phase 6 is recorded (the `tl2`
runs must compare one fixed candidate with their baselines). `docs/plans/` also holds the stabilization, frontend,
traffic-link and JIT plans.
Touches ADR-045 (model per role + amendments 1–3), ADR-052 (acceptance rule), ADR-037 amendment 2 (data sent to
providers), ADR-063 (dependencies, lint), ADR-064 (the LLM quota shared across processes).

## 0. What is true today (existing, read 2026-11-13)

**Already flexible (keep):**
- No graph, tool, skill or prompt names a model. Every call goes `graph → roles.Role → llm.LLM`
  (`pipelines/agents/roles.py`, `pipelines/agents/llm.py`); a role is an ordered tuple of candidates, main first.
- Availability → the next candidate; validity → one retry on the same model, then stop (`roles.py`).
- Numbers come from code (slots, validators); the claim guards are code. A different model changes wording, not
  arithmetic.
- The reply cache key holds provider, model, params, messages, tools, schema and method (`llm.LLM.key`), so a new
  model never reads another model's cached replies.
- The evaluation scripts read `roles.ROLES` and write the models into every results file.

**What falls over when a model is changed (each one found in the code or in the runs of 2026-11-12 / 13):**

| # | Weakness | Where | What happens on a swap |
|---|---|---|---|
| W1 | The model per role is Python constants | `roles.py` `QWEN / FLASH_LITE / GPT_OSS_20B / NEMOTRON`, `ROLES` | A swap is a code edit; `Weekly_pack_check.py` pins the three pairs as text, so it fails until edited too. |
| W2 | Three providers, wired by `if` | `llm.chat_model`, `llm.available_models`, `PROVIDERS` | Anthropic, OpenAI direct, a local server or any other provider needs new branches in three functions. |
| W3 | Limits belong to the provider, at free-tier values | `PROVIDERS`: Gemini 10 requests / minute, OpenRouter 50 / day for every model | A paid key is throttled or stopped locally by a limit it no longer has (a paid OpenRouter model would stop after 50 requests a day). |
| W4 | `temperature = 0` is sent to every model | `llm.chat_model` | flash-lite already ignores it with a warning; some reasoning models refuse a request that sets it. |
| W5 | One timeout for all models | `llm.TIMEOUT_S = 120` | A slower, stronger model times out and is read as an outage. |
| W6 | The structured-output method is known only for today's four models | `roles.Candidate.method` | A new model needs its method found by trial; a wrong one gives two invalid replies → the run stops. |
| W7 | A 5xx on the same request in two runs is cached as a permanent failure | `llm.REPEATED_SERVER_RUNS = 2` | During an outage of hours (Gemini 503, 2026-11-12) a re-run turns outage errors into cached failed items. Any new provider with a bad day triggers it. |
| W8 | No spend limit | `llm.QuotaState` counts requests only | Free tiers stop by themselves; a paid model does not. A loop or a long evaluation costs real money unnoticed. |
| W9 | A swap has no procedure | — | Nothing says which checks prove a new model before it serves a pack; ADR-052 covers only the final evaluation. |
| W10 | The fallback is a different, weaker model | `ROLES` | When the main model is down the output changes character (tl1: 32 of 66 calls on the fallback). Not a bug — but it must be visible per run, and the fallback must pass the same proof as the main model. |

Comments that name a model (`weekly_pack.py` `MAX_REVISES`, `memory.py`, `Memory_check.py`, `Api_smoke.py`) are
wording only and are corrected in passing.

## 1. Owner decisions

| # | Decision | Chosen | Not chosen |
|---|---|---|---|
| M1 | Where the model per role is set | **One tracked file in the project** — reviewed, in git history | The file + `.env` overrides; staying in code |
| M2 | Which providers to prepare for | **Any model from anywhere** — a provider is an entry, not a code branch | A fixed list (paid OpenRouter / paid Gemini / Anthropic / OpenAI) |
| M3 | When | **Plan now, implementation after traffic Phase 6** | Everything after Phase 6 |

**Decisions M4–M7 — the recommended answer of each was approved with the plan (2026-11-13):**

| # | Decision | Recommended | Alternative |
|---|---|---|---|
| M4 | Evaluating a candidate model without editing the reviewed file | The evaluation scripts alone accept `EVAL_MODELS=<file>` (a second TOML); the API, the CLIs and the scheduler always read the tracked file. Every results file already records its models. | Edit the tracked file for each trial and restore it. |
| M5 | Spend limit for paid models | A per-model `max_usd_per_day` in the file; reaching it raises `Exhausted` like a free quota (the fallback answers). Prices are entered by hand per model. | No limit; only a cost line in the run record. |
| M6 | New provider libraries | None now. The OpenAI-compatible adapter (already installed) reaches OpenRouter, Groq, OpenAI, and most hosted or local servers; a native library (for example `langchain-anthropic`) is added with `uv add` only when a model is actually chosen that needs it. | Install the native libraries now. |
| M7 | The repeated-5xx rule (W7) | Keep the rule, add an outage test: a failure counts toward "a property of the request" only if the same model answered another request in that run. | Remove the rule; or leave it and avoid re-runs by hand. |

## 2. Design

### 2a. The file — `pipelines/agents/models.toml` (tracked, loaded with the standard library `tomllib`)

```toml
# One entry per model; one line per role. Changing the main model or the fallback = editing [roles].
[providers.gemini]
adapter = "gemini"                     # gemini | groq | openai_compatible | langchain
key_env = "GEMINI_API_KEY"
day_tz  = "America/Los_Angeles"

[providers.openrouter]
adapter  = "openai_compatible"
key_env  = "OPENROUTER_API_KEY"
base_url = "https://openrouter.ai/api/v1"
day_tz   = "UTC"

[models.flash_lite]
provider   = "gemini"
id         = "gemini-3.5-flash-lite"
structured = "function_calling"        # function_calling | json_schema | json_mode
temperature = 0                        # omit the key for a model that refuses it (W4)
timeout_s  = 120
limits     = { rpm = 10, tpm = 250000, scope = "model" }   # no rpd, as today: Gemini's own 429 decides

[models.nemotron]
provider   = "openrouter"
id         = "nvidia/nemotron-3.5-super-vl:free"
structured = "function_calling"
limits     = { rpm = 20, tpm = 1000000, rpd = 50, scope = "provider" }

# a paid model, for illustration only — nothing is bought by this plan
# [models.strong]
# provider = "openrouter"
# id = "<vendor>/<model>"
# structured = "json_schema"
# limits = { rpm = 60, tpm = 2000000 }                # no rpd: the provider's own 429 decides
# price_usd_per_mtok = { input = 0.0, output = 0.0 }  # entered by hand from the provider's price page
# max_usd_per_day = 2.0

[roles]
insight = ["flash_lite", "nemotron"]   # main first, then the fallbacks, any length
writer  = ["flash_lite", "nemotron"]
tools   = ["flash_lite", "gpt_oss_20b"]
```

- **Limits move from the provider to the model** (W3): `rpm / tpm / rpd / scope` per entry; no `rpd` = no local daily
  stop. The day's time zone stays with the provider.
- **Adapters** (W2, M2): `gemini` and `groq` keep today's LangChain classes; `openai_compatible` is today's
  OpenRouter path with `base_url` from the file (OpenAI, Together, Fireworks, DeepSeek, a local Ollama / vLLM
  server…); `langchain` calls `init_chat_model(id, model_provider=…)` for a provider whose integration package is
  installed. A new provider = a `[providers.x]` block, no code.
- **Loaded once and validated** (`roles.load_models`): unknown provider / adapter / structured method, a role with
  no candidate, a role whose every candidate lacks its key → one error at start-up that names the entry, not a
  failure in the middle of a pack.
- **Cache keys do not move** for today's four models: the key payload keeps `provider`, `model` and `params` as
  they are now, so the existing caches and every recorded baseline stay valid. Proved by a check (2c).
- `roles.ROLES` stays as the name the evaluation scripts read; it is built from the file.

### 2b. Robustness that does not depend on the model

- **W4 / W5:** `temperature` and `timeout_s` per model; a key that is absent is not sent.
- **W7 (M7):** outage-aware repeated-failure rule.
- **W8 (M5):** cost per call = tokens × the entry's price, added to the usage record and to `usage.json` per day;
  `max_usd_per_day` stops the model like a quota. Free models have no price and cost 0.
- **W10:** every run record already lists the model of each call; the pack's `run.json`, the API's run view and
  the evaluation aggregate gain one number — the share of calls answered by a fallback — so a degraded day is
  seen, not inferred.

### 2c. Proof before a model serves anything — `pipelines/scripts/agents/Model_probe.py` (new)

One command per candidate: `uv run python tools/run.py pipelines/scripts/agents/Model_probe.py -- <model key>`.
About 12 real calls, public or synthetic prompts only (ADR-037 amendment 2):

1. the provider serves the id (model list; no generation quota);
2. one tool call with the project's real tool schemas (`finance_kpi`, `search_documents`);
3. structured output with each method on the project's real schemas — `InsightNotes`, `DeckDraft`, `QaAnswer`,
   the approver request — and which method validates (W6);
4. `temperature = 0` accepted, ignored or refused (W4);
5. one Egyptian Arabic question answered in Arabic;
6. the largest reviewed request (`Supervisor_check`: 7,404 est. tokens; the pack Writer: ≈ 17K) fits and returns
   inside `timeout_s` (W5).

It prints the `[models.x]` entry to paste and a pass / fail per line. It changes nothing.

### 2d. The swap procedure (W9) — `docs/model_swap.md` (new, one page)

1. Add the model's entry; run `Model_probe.py` → all lines pass.
2. Fake-model checks (0 calls): `Weekly_pack_check`, `Deck_check`, `Finance_qa_check`, `Supervisor_check`,
   `Traffic_claims_check`, lint — they prove the wiring, not the model.
3. A small real run on the candidate (`EVAL_MODELS`, M4): `Weekly_pack_check` Phase 5 (4 weeks) + `Api_smoke`.
4. ADR-052: `Stage1_eval` (packs + Q&A) and `Stage2_eval`, twice, against the current baselines.
5. Keep → edit `[roles]`, record an ADR-045 amendment, the results file becomes the baseline. Reject → the file is
   untouched.

A fallback model passes steps 1–3; step 4 is run with the fallback forced as main for the packs scope once
(the existing forced-fallback test of ADR-045 amendment 2).

## 3. Phases

| # | Work | Done when |
|---|---|---|
| 1 | `models.toml` with today's four models and three roles; `roles.load_models` + validation; `llm.py` reads limits, adapter, temperature, timeout from the entry; `PROVIDERS` removed or reduced to a view | Every existing fake-model check passes unchanged; a new `Models_config_check.py` proves: the loaded roles = ADR-045's pairs, **every cache key of today's models is byte-equal to the key before the change** (computed on recorded requests), bad files are refused with the entry's name |
| 2 | Adapters `openai_compatible` (generic `base_url`) and `langchain`; limits per model; no-`rpd` paid entries | `Models_config_check` drives each adapter with a stub server / stub class: request shape, key header, errors classified as today |
| 3 | W7 outage-aware rule; W8 cost + `max_usd_per_day`; W10 fallback share in run records | Stub-model tests: an outage does not cache failures, a request-specific 5xx still does; a priced stub stops at its cap and the fallback answers; the share is in `run.json` and the API view |
| 4 | `Model_probe.py` + `docs/model_swap.md`; `Weekly_pack_check`'s pinned pairs read from the file's reviewed `[roles]` | The probe passes on the four current models (≈ 48 calls, one free day); the swap page walked through once on paper |
| 5 | No-regression: `Stage1_eval` (packs + Q&A) and `Stage2_eval`, real models, against the baselines current at that time; ADR + `ARCHITECTURE.md` §8 + ROADMAP; archive | ADR-052 "tie" (the models did not change, only how they are configured); the owner's commit |

Phases 1–4 spend no model quota except the probe (Phase 4). Phase 5 is one evaluation of two provider days.

## 4. Out of scope

- Choosing or buying a stronger model. This plan makes the change safe; which model, and whether it is worth its
  price, is a later ADR-045 amendment with its own ADR-052 evaluation.
- The embedding model (ADR-037) and the reranker (ADR-038): they have their own bake-off and stored vectors; a
  swap there means re-embedding the corpus.
- Prompt tuning per model. If a stronger model needs different prompts, that is a candidate change under ADR-052.
- Routing by cost or difficulty (cheap model first, strong model on failure): possible on top of this file, not
  designed here.

## 5. Risks

- **A silent change of cache keys** would orphan the caches and make the next evaluation re-spend every call. The
  byte-equality check of Phase 1 is the guard.
- **A model that passes the probe but writes differently** (longer sentences, other phrasings) meets the regex
  claim guards and the deck Validator. Since D-TL-11 a refused traffic sentence is repaired, not fatal; the
  ADR-052 run in the swap procedure is what measures the rest.
- **A paid key in `.env`** is a real cost. `max_usd_per_day` (M5) and the per-run cost line are the controls; the
  threat model gains a row.

## Progress / deviations

- 2026-11-13 — plan written PROPOSED. Facts read in `roles.py`, `llm.py`, the three evaluation scripts and
  `Weekly_pack_check.py`; W7 and W10 observed in the traffic Phase 6 runs of 2026-11-12 / 13. Nothing implemented.
- 2026-11-13 — **APPROVED** by the owner ("موافق") with the recommended answers: M4 `EVAL_MODELS` for the
  evaluation scripts only, M5 `max_usd_per_day` per model, M6 no new provider library now, M7 the outage-aware
  repeated-failure rule. Implementation waits for traffic Phase 6 to be recorded (M3).
- 2026-11-15 — **Phase 1 started** (owner, clickable: "all phases now"; traffic Phase 6 closed 2026-11-14).
  Handoff: `pipelines/agents/models.toml` (four models, three roles = ADR-045, provider defaults + bake-off
  candidates) and `pipelines/agents/model_config.py` (loader + validation, `use()` for EVAL_MODELS) written; the
  loader parses the file. **Deviation:** the loader is its own module (not `roles.load_models`) so `llm.py` and
  `roles.py` can both read it without an import cycle. **Not yet wired:** nothing imports it — `llm.py` (limits /
  adapter / temperature / timeout per entry; cache-key params unchanged for temperature 0) and `roles.py` (ROLES
  built from `[roles]`, key check in `Roles()`) are unchanged; next: that wiring + `Models_config_check.py`
  (byte-equal cache keys vs the legacy payload), then Phases 2–5. W7 design note: "answered another request" =
  a fresh success of the same model in this process within the last 30 min.
- 2026-11-15 — same session, outside this plan: `Stage1_eval.py` records `degraded` + `draft_origin` per pack and
  `degraded_packs` in the aggregate (Phases 1–4 ✅, new asserts: 0 in Phase 3, 11 in Phase 3c). Owner decisions the
  same day: stabilization / frontend gates → Claude prepares the full-data clone script + Power BI parity by MCP,
  W17 decided in the UI with one approver change; JIT plan deferred (after this plan); the pack's rewrite load
  deferred. Pushed CI green: run 43690050303 (checks, web incl. Playwright 130 passed / 50 skipped,
  api-integration). These still need recording in ROADMAP and the two other plans.
- 2026-11-15 — **Phases 1–4 done** (owner: "كمّل خطة المرونة"). Handoff:
  - **Phase 1:** `llm.py` reads providers (adapter, key variable, quota day, base URL, default limits, bake-off
    candidates) and per-model limits / temperature / timeout from the file (`llm.limits`, `llm.chat_kwargs`,
    `llm.PROVIDERS` rebuilt by `reload_providers`); `roles.ROLES` built from `[roles]`; `roles.reload` /
    `roles.use_eval_models` (M4, read by `Stage1_eval`, `Stage2_eval`, `Weekly_pack_check`; results files record
    `models_file`); `roles.NoModelKey` (an `Exhausted`) when a role has no key. The model constants of `roles.py` are
    gone (nothing outside it used them). New `Models_config_check.py` Phase 1: roles / providers / limits / kwargs =
    the pre-file values, **48 cache keys byte-equal** to the pre-file payload, 8 broken files refused naming the
    entry, EVAL_MODELS switch and back, keyless role refused. Fake-model checks after the wiring, all exit 0:
    Weekly_pack_check (10 lines), Deck_check (9), Finance_qa_check (6), Supervisor_check (9), Traffic_claims_check
    (6), Stage1_eval Phases 1–4 (6), Stage2_eval Phases 1–3 (4), Approval_safety_check (5), Run_lifecycle_check (4),
    Load_test (6, its stub provider still injected through `llm.PROVIDERS`).
  - **Phase 2:** adapters `openai_compatible` (any base URL; Groq's model list now from its base URL too) and
    `langchain` (`init_chat_model`, `lc_provider`). `Models_config_check` Phase 2 against a stub OpenAI-style server
    on 127.0.0.1: request shape, the key only in the Authorization header, temperature sent / not sent (W4), the model
    list, 429 day / minute, 400, 404 classified as before.
  - **Phase 3:** W7 / M7 — a 5xx counts toward a cached "repeated server failure" only if the same model gave a fresh
    answer in this process within 30 min (`RECENT_OK_S`); W8 / M5 — `llm.cost_usd`, `QuotaState.spend` /
    `add_spend` (`spend.json`, per provider day and model), the cap checked with the quota, `cost_usd` in every role
    usage record; W10 — `roles.fallback_share` in the pack's `run.json` (+ `cost_usd`), the API's `PackView`
    (`fallback_share`, shown in Reports when above 0; OpenAPI + client regenerated, packs spec 8 / 8), and per item
    in both evaluations' usage (+ `cost_usd` summed in the aggregates). `Models_config_check` Phase 3: outage not
    counted or cached; request-specific 5xx cached on its second run, then not sent; a priced stub spent 0.021 USD and
    stopped at its 0.02 cap, the fallback answered; share 0.25. Lint ruff 0 / pyright 0.
  - **Phase 4:** `Model_probe.py` (6 lines per model, ~7 real calls; `PROBE_MODELS`, `EVAL_MODELS`; the size line is
    capped at 75 % of the model's per-minute token limit — Groq's 8K TPM cannot take 17K, ADR-045 am. 3) — real
    probe 2026-11-15 of the four entries: flash-lite, nemotron, gpt-oss-20b, qwen **all pass every line**
    (structured: flash-lite all 3 methods, nemotron function_calling + json_schema, gpt-oss-20b json_schema only,
    qwen function_calling + json_schema — each entry's method among them; Arabic answered in Arabic by all four);
    about 28 calls. `docs/model_swap.md` written; `Weekly_pack_check`'s pinned pairs now read from the file's
    `[roles]` (the tracked file itself is pinned to ADR-045 by `Models_config_check`).
  - **Deviations:** the loader is `model_config.py`, not `roles.load_models` (no import cycle); the probe's size line
    is capped per model; the evaluation aggregate carries `fallbacks` + `calls` (share per item and in `run.json` /
    `PackView`); the model-naming comments of `weekly_pack.py` / `memory.py` / `Memory_check.py` / `Api_smoke.py`
    were left as they are (wording only).
  - **Phase 5 done:** see the implementation record at the top.
