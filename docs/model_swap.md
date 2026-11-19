# Changing a model — the swap procedure

The model of each agent role (ADR-045) is set in one tracked file, `pipelines/agents/models.toml` (Model flexibility
plan, owner decisions M1–M7). Changing the **main** model or a **fallback** of a role is an edit of its `[roles]`
line — no code. This page is the order of proof before a new model serves a pack, an answer or a watch brief.

## 0. Before you start

- **Which model, and is it worth its price?** That choice is not made here: it is an ADR-045 amendment backed by the
  evaluation of step 4.
- **A paid model is a real cost.** Give it `price_usd_per_mtok` (from the provider's price page) and a
  `max_usd_per_day`; at the cap the model stops for the day like a free quota and the role's fallback answers.
- **A new provider** = a `[providers.<name>]` block: `adapter = "openai_compatible"` with its `base_url` reaches most
  hosted or local servers (OpenAI, OpenRouter, Together, DeepSeek, Ollama, vLLM…). A provider that needs its own
  LangChain package uses `adapter = "langchain"` + `lc_provider`, after `uv add <package>==<version>` (M6).
- **The key** goes in `.env` under the block's `key_env` name — never in the file.

## 1. Probe the model (≈ 12 real calls, nothing changes)

```powershell
uv run python dev/tools/run.py dev/checks/agents/Model_probe.py -- <model entry name>
```

It checks: the provider serves the id; one tool call on the project's real tool schema; structured output with each
method on the project's real schemas (which one validates → the entry's `structured`); whether `temperature = 0` is
accepted, ignored or refused; an Egyptian Arabic question answered in Arabic; the largest reviewed request (the pack
Writer, ≈ 17K tokens) inside `timeout_s`. It prints a pass / fail per line and the entry to paste.

## 2. Fake-model checks (0 model calls) — the wiring, not the model

```powershell
uv run python dev/tools/run.py dev/checks/agents/Models_config_check.py
uv run python dev/tools/run.py dev/checks/agents/Weekly_pack_check.py
uv run python dev/tools/run.py dev/checks/agents/Deck_check.py
uv run python dev/tools/run.py dev/checks/agents/Finance_qa_check.py
uv run python dev/tools/run.py dev/checks/agents/Supervisor_check.py
uv run python dev/tools/run.py dev/checks/agents/Traffic_claims_check.py
uv run python dev/tools/lint_ratchet.py
```

## 3. A small real run on the candidate, without editing the reviewed file (M4)

Put a copy of `models.toml` with the candidate in `[roles]` somewhere outside the repository, then:

```powershell
$env:EVAL_MODELS = 'C:\path\to\candidate_models.toml'; $env:PACK_REAL_MODELS = '1'
uv run python dev/tools/run.py dev/checks/agents/Weekly_pack_check.py
Remove-Item Env:EVAL_MODELS, Env:PACK_REAL_MODELS
```

`EVAL_MODELS` is read by the evaluation scripts only (`Weekly_pack_check`, `Stage1_eval`, `Stage2_eval`); the API, the
CLIs and the scheduler always read the tracked file.

## 4. ADR-052 — the decision

`Stage1_eval` (packs + Q&A) and `Stage2_eval` with the same `EVAL_MODELS`, `EVAL_REAL_MODELS=1`, twice, against the
current baselines (`docs/ROADMAP.md` names them). Every results file records its models and the share of calls a
fallback answered (`fallback_share`).

## 5. Keep or reject

- **Keep:** edit `[roles]` in the tracked file, write the ADR-045 amendment, the results file becomes the baseline,
  one commit.
- **Reject:** the tracked file is untouched; record the result in the plan or ADR that asked for it.

A **fallback** model passes steps 1–3; for step 4 it is forced as the main once on the packs scope (put it first in the
candidate file's `insight` / `writer` lines), the forced-fallback test of ADR-045 amendment 2.
