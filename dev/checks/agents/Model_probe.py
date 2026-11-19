"""Model probe — the proof a model gives before it serves any role (Model flexibility plan §2c, docs/model_swap.md).

Plan:    docs/plans/Model_flexibility_plan.md Phase 4 (approved 2026-11-13).
Run:     uv run python dev/tools/run.py dev/checks/agents/Model_probe.py
         $env:PROBE_MODELS = 'flash_lite,nemotron'   (entry names of models.toml; default: every model of [roles])
         $env:EVAL_MODELS = '<candidate file>'       (optional: probe a model of a candidate file, M4)
Reads:   pipelines/agents/models.toml (or EVAL_MODELS); .env (the keys); the project's real tool and answer schemas.
Calls:   about 7 real requests per model (public or synthetic prompts only, ADR-037 amendment 2), counted in the shared
         daily quota; replies cached in dev/_scratch/model_probe_cache/ (git-ignored), so a re-run is free.
Writes:  that cache only. Changes nothing else.
Re-run:  safe.

Lines per model (pass / fail / note)
1. served   — the provider lists the id (model list: no generation quota).
2. tool     — one tool call on the project's real `finance_kpi` schema, with the right name and a week argument.
3. methods  — structured output with function_calling / json_schema / json_mode on a small project schema
               (`Verdict`): which validate; the entry's `structured` must be one of them.
4. answer   — the entry's method on `QaAnswer` (the finance Q&A answer), validated.
5. arabic   — an Egyptian Arabic question answered in Arabic script.
6. large    — a ~17K-token request (the size of the pack Writer's prompt; capped at 75 % of the model's per-minute
               token limit) answered inside the entry's timeout_s.
temperature — every request above sends the entry's temperature; a refusal would fail lines 2–6 as bad_request.
Final Checkpoint: one line per model; exit 1 if a model fails a line.
"""
# %% Setup
import os
import re
import sys
import time
from pathlib import Path

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402

from pipelines.agents import llm, model_config, roles  # noqa: E402
from pipelines.agents.graphs.models import QaAnswer, Verdict  # noqa: E402
from pipelines.agents.tools.finance import finance_kpi_tool  # noqa: E402
from pipelines.lib.common import load_env  # noqa: E402

load_env(ROOT)
used = roles.use_eval_models()
cfg = model_config.current()
names = [n.strip() for n in (os.environ.get("PROBE_MODELS") or "").split(",") if n.strip()] or \
    list(dict.fromkeys(n for role in cfg.roles.values() for n in role))
unknown = [n for n in names if n not in cfg.models]
assert not unknown, f"not in {cfg.path.name}: {unknown}"
CACHE = ROOT / "dev" / "_scratch" / "model_probe_cache"
quota = llm.QuotaState()                       # the shared daily counts: a probe call is a real call
print(f"models file: {cfg.path.name}{' (EVAL_MODELS)' if used else ''}; probing {names}")
ARABIC = re.compile(r"[؀-ۿ]")
# a public, synthetic filler for the size test: the Suez tariff's band names repeated (no project data)
LINE = "Band {}: SDR {}.{:02d} per SCNT ton for laden vessels; ballast at a lower rate."
LARGE_TOKENS = 17_000          # the pack Writer's largest reviewed prompt (Agents plan Phase 5 S6)


def filler(tokens: int) -> str:
    out, i = [], 0
    while llm.est_tokens(" ".join(out)) < tokens:
        out.append(LINE.format(i % 8, i % 13, i % 97))
        i += 1
    return " ".join(out)


def line(results: dict, name: str, ok: bool | None, note: str) -> None:
    results[name] = ok
    print(f"   {'✓' if ok else ('–' if ok is None else '✗')} {name:<8} {note}")


def call(m: llm.LLM, messages, **kw):
    t0 = time.perf_counter()
    try:
        reply = m.invoke(messages, **kw)
    except llm.Exhausted as e:
        return None, f"exhausted: {str(e)[:140]}", 0.0
    return reply, None, time.perf_counter() - t0


# %% Probe
summary = {}
with httpx.Client(timeout=30) as client:
    for name in names:
        e = cfg.models[name]
        res: dict[str, bool | None] = {}
        print(f"\n{name} = {e.provider}/{e.id} (structured {e.structured}, temperature {e.temperature}, "
              f"timeout {e.timeout_s:.0f} s)")
        if not llm.has_key(e.provider):
            line(res, "served", False, f"{llm.PROVIDERS[e.provider]['key']} is not in .env")
            summary[name] = res
            continue
        try:
            served = e.id in llm.available_models(e.provider, client)
            line(res, "served", served, "listed by the provider" if served else "not in the provider's model list")
        except Exception as exc:  # noqa: BLE001 — reported as the line's result
            line(res, "served", False, f"model list failed: {str(exc)[:120]}")
        m = llm.LLM(e.provider, e.id, cache_dir=CACHE, quota=quota)

        r, why, _ = call(m, [HumanMessage("How much did PortPilot bill in report week 23 of 2025? Use the tool.")],
                         tools=[finance_kpi_tool])
        calls = (r.message.tool_calls if r and r.ok and r.message is not None else []) or []
        good = bool(calls) and calls[0]["name"] == "finance_kpi" and calls[0]["args"].get("report_week") == 23
        line(res, "tool", good, why or (f"called {calls[0]['name']}({calls[0]['args']})" if calls
                                        else f"no tool call ({(r.error or {}).get('kind') if r else ''})"))

        ok_methods = []
        for method in ("function_calling", "json_schema", "json_mode"):
            r, why, _ = call(m, [HumanMessage("Return a verdict for a slide whose numbers all match their evidence: "
                                              "it passed, with no problems. Answer as JSON with the fields of the "
                                              "schema.")], schema=Verdict, method=method)
            if r is not None and llm.parse_structured(r, Verdict)[0] is not None:
                ok_methods.append(method)
        line(res, "methods", e.structured in ok_methods,
             f"valid with {ok_methods or 'none'}; the entry says {e.structured}")

        r, why, _ = call(m, [SystemMessage("Answer finance questions from the evidence only. Evidence insight.w23: "
                                           "billed_sdr = 8394785.98 for report week 23."),
                             HumanMessage("What did PortPilot bill in week 23? Cite the evidence id.")],
                         schema=QaAnswer, method=e.structured)
        obj, why2 = llm.parse_structured(r, QaAnswer) if r is not None else (None, why)
        line(res, "answer", obj is not None, why2 or f"{obj.status}, evidence {obj.evidence_ids}")

        r, why, _ = call(m, [HumanMessage("لو سمحت قولّي في جملة واحدة: يعني إيه ميناء؟")])
        text = llm.message_text(r.message) if r and r.ok and r.message is not None else ""
        line(res, "arabic", bool(ARABIC.search(text)), why or text[:60].replace("\n", " "))

        # capped below the model's per-minute token limit: a larger request can never pass there (Groq 8K TPM;
        # ADR-045 amendment 3: such requests are served by the role's main model alone)
        target = min(LARGE_TOKENS, int(e.limits["tpm"] * 0.75))
        text_l = filler(target)
        r, why, secs = call(m, [SystemMessage(text_l), HumanMessage("In one short sentence: what is this list about?")])
        size = llm.est_tokens(text_l)
        line(res, "large", bool(r and r.ok), why or (f"~{size:,} tokens, {r.latency_ms or 0:.0f} ms"
                                                     + (" (cached)" if r and r.cached else "") if r and r.ok
                                                     else f"failed: {(r.error or {}).get('kind') if r else ''}"))
        summary[name] = res


# %% Final Checkpoint
failed = {n: [k for k, v in r.items() if v is False] for n, r in summary.items()}
failed = {n: k for n, k in failed.items() if k}
print("\nFinal Checkpoint:", {n: "pass" if n not in failed else f"fail {failed[n]}" for n in summary})
assert not failed, f"probe failed: {failed}"
print(f"✅ Final Checkpoint passed: {len(summary)} model(s) pass every probe line ({cfg.path.name})")
