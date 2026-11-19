# Models_config_check — Final Checkpoint

Script: `dev/checks/agents/Models_config_check.py` (Model flexibility plan, `docs/plans/Model_flexibility_plan.md`).
No database, no model call, no network beyond a stub server on 127.0.0.1 that the script starts and stops.

## What it proves

1. **The tracked file is ADR-045.** `pipelines/agents/models.toml` gives the same roles, models and structured
   methods as the constants `roles.py` held before (written in the check by hand from commit 68a8d3b), the same
   provider registry (`llm.PROVIDERS`: key variables, quota days, base URL, bake-off candidates) and, per model, the
   same limits, temperature 0, 120 s timeout and no library retries.
2. **Cache keys did not move.** For each of the four models, 3 conversations × 4 request shapes (plain, with a tool,
   structured with two methods) — 48 keys — equal the key computed with the payload as written before the file. The
   existing replies in `Data/processed/agents/eval/llm_cache/` and every recorded baseline stay valid; a re-run of an
   evaluation on unchanged prompts spends no quota.
3. **A wrong file fails at start-up, naming the entry** (8 broken copies: unknown adapter, a role naming a missing
   model, an empty role, an unknown method, a spend cap without a price, an OpenAI-compatible provider without a base
   URL, two entries for one model, a zero per-minute limit).
4. **EVAL_MODELS** switches an evaluation process to another file and back (M4); **a role with no key** is refused when
   the real roles are built (`roles.NoModelKey`, an `Exhausted`: the API answers 503).
5. **Adapters (Phase 2):** `openai_compatible` with any base URL and `langchain` (`init_chat_model`) talk to the stub:
   the model id and messages in the request body, the key only in the Authorization header, temperature sent or not
   sent as the entry says, the model list read; 429 per-day / per-minute, 400, 404 classified as before.
6. **Robustness (Phase 3):** an outage — a model that has not answered anything in this process — is not counted
   toward a cached "repeated server failure" (W7, M7); a request-specific 5xx still is on its second run and is then
   not sent again; a priced model stops at its `max_usd_per_day` and the role's fallback answers (W8, M5); the share
   of calls answered by a fallback is computed from the usage records (W10).

## Problems met and fixes

- The temperature read from TOML is a float (`0.0`): the cache key keeps the legacy params because the comparison is
  numeric (`== 0`), and the clients receive `0.0`, which every provider accepts as before.
