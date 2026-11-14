"""Approver request evaluation (approver-request plan R4, owner 2026-11-07): does the one structured call read the
Finance manager's words as the right changes to the waiting pack?

Run:     uv run python tools/run.py pipelines/scripts/agents/Approver_request_eval.py   (from the project root)
         APPROVER_EVAL_OFFLINE=1 → Phase 1 only (no model call)

Reads:   `Data/processed/agents/eval/approver_request_golden.jsonl` (30 requests, 15 EN + 15 Egyptian AR, frozen
         2026-11-07 before the first real run) and `approver_request_draft.json` (W14's draft, notes and evidence,
         frozen the same day from `weekly_pack:live:2025-W14:1`, which the 30-day retention will delete); both SHA-256
         checked against FROZEN. The `tools` role's models (ADR-045; llm.py cache and quota: ≈ 30 requests the first
         time, cached after). No database, no graph run: nothing is applied.
Writes:  `Data/processed/agents/eval/approver_request_eval_<date>.json`.
Re-run:  safe (the replies are cached: a re-run scores the same proposals).

Gates (R4, fixed before the run):
- exact interpretation ≥ 0.90 over the 30, and Arabic ≥ English − 0.10;
- invented numbers 0: every number in a proposed text (edit, addition, analysis note, steer) appears in the request
  or in the draft the manager is looking at.
"Exact" compares the action; the charts after the catalogue's defaults (series as a set); the slides of the additions;
the bullets of the edits; the analysis edits' (target, op, index); whether there is a steer; and an ask-back when the
request cannot be placed or breaks the catalogue's week rule. Texts are not compared (the Validator binds their
numbers when they are applied).
"""
# %% Setup
import hashlib
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from pipelines.agents import approver_request as ar  # noqa: E402
from pipelines.agents.deck import charts as C  # noqa: E402
from pipelines.lib import common  # noqa: E402

common.load_env(ROOT)
EVAL = ROOT / "Data" / "processed" / "agents" / "eval"
GOLDEN, DRAFT = EVAL / "approver_request_golden.jsonl", EVAL / "approver_request_draft.json"
FROZEN = {"golden": "2ddd0d07c4415147", "draft": "a16be270c9678135"}
GATE, AR_MARGIN = 0.90, 0.10
DONE: list[int] = []

# %% Phase 1 — the frozen inputs (no model call)
raw_g, raw_d = GOLDEN.read_bytes(), DRAFT.read_bytes()
sha = {"golden": hashlib.sha256(raw_g).hexdigest()[:16], "draft": hashlib.sha256(raw_d).hexdigest()[:16]}
assert sha == FROZEN, f"a frozen input changed: {sha} (REFREEZE only with the owner)"
items = [json.loads(x) for x in raw_g.decode("utf-8").splitlines()]
state = json.loads(raw_d)
assert len(items) == 30 and len({i["id"] for i in items}) == 30, "the frozen set changed shape"
assert sum(i["lang"] == "en" for i in items) == 15, "15 English + 15 Arabic"
kinds = {i["expected"]["action"] for i in items}
assert kinds == {"change", "approve", "reject", "ask_back"}, kinds
VIEW = ar.view_of(state)
print(f"Phase 1: 30 requests (15 EN / 15 AR), actions {sorted(kinds)}, draft of week {state['report_week']} "
      f"({len(state['draft']['bullets'])} bullets)")
print("✅ Phase 1 validation passed: the frozen set and the frozen draft match their SHA-256")
DONE.append(1)


def chart_key(c: dict) -> tuple:
    full = C.resolve({**C.DEFAULTS[c["chart"]], **{k: v for k, v in c.items() if v is not None}})
    return (full["chart"], tuple(sorted(full.get("series") or [])), full.get("weeks"), full.get("measure"),
            full.get("rows"))


def norm(e: dict) -> dict:
    return {"action": e["action"], "charts": sorted(chart_key(c) for c in e["charts"]),
            "additions": sorted(e["additions"]), "edits": sorted(e["edits"]),
            "analysis": sorted(tuple(a) for a in e["analysis"]), "steer": bool(e["steer"]),
            "ask_back": bool(e["ask_back"])}


def got_of(p: ar.Proposal) -> dict:
    out = {"action": "change", "charts": [], "additions": [], "edits": [], "analysis": [], "steer": False,
           "ask_back": False}
    if p.ask_back or not p.steps:
        return {**out, "action": "ask_back", "ask_back": True}
    if p.steps[0]["decision"] in ("approve", "reject"):
        return {**out, "action": p.steps[0]["decision"]}
    for s in p.steps:
        out["charts"] += s.get("charts") or []
        out["additions"] += [a["slide"] for a in s.get("additions") or []]
        out["edits"] += [e["bullet"] for e in s.get("edits") or []]
        out["analysis"] += [[e["target"], e["op"], e.get("index")] for e in s.get("analysis_edits") or []]
        out["steer"] = out["steer"] or bool(s.get("steer"))
    return out


NUM = re.compile(r"\d+(?:\.\d+)?")


def numbers(text: str) -> set[str]:
    return {n.rstrip("0").rstrip(".") if "." in n else n for n in NUM.findall(text.replace(",", ""))}


def invented(p: ar.Proposal, request: str) -> list[str]:
    seen = numbers(request) | numbers(VIEW)
    texts = [x.get("text") or "" for s in p.steps for k in ("edits", "additions", "analysis_edits")
             for x in s.get(k) or []] + [s.get("steer") or "" for s in p.steps]
    return sorted({n for t in texts for n in numbers(t)} - seen)


# %% Phase 2 — the real model on the 30 requests
if os.environ.get("APPROVER_EVAL_OFFLINE") == "1":
    print("✅ Final Checkpoint: Phase 1 only (APPROVER_EVAL_OFFLINE=1)")
    raise SystemExit(0)
from pipelines.agents import roles as roles_mod  # noqa: E402

models = roles_mod.Roles()
rows, calls, inv = [], 0, []
for it in items:
    p = ar.propose(it["request"], state, models)
    calls += p.model_calls
    got = got_of(p)
    bad = invented(p, it["request"])
    if bad:
        inv.append((it["id"], bad))
    rows.append({"id": it["id"], "lang": it["lang"], "request": it["request"], "expected": it["expected"],
                 "got": got, "understood": p.understood, "ask_back": p.ask_back, "steps": p.steps,
                 "right": norm(got) == norm(it["expected"]), "invented": bad})


def rate(sel):
    sel = list(sel)
    return round(sum(r["right"] for r in sel) / len(sel), 4) if sel else None


en, ar_ = rate(r for r in rows if r["lang"] == "en"), rate(r for r in rows if r["lang"] == "ar")
asks = [r for r in rows if r["expected"]["ask_back"]]
result = {"date": date.today().isoformat(), "frozen": sha, "exact": rate(rows), "exact_en": en, "exact_ar": ar_,
          "ask_back_recall": rate(asks), "invented": inv, "model_calls": calls,
          "gate": {"exact_ge_0_90": (rate(rows) or 0) >= GATE, "ar_ge_en_minus_0_10": (ar_ or 0) >= (en or 0) - AR_MARGIN,
                   "invented_0": not inv},
          "wrong": [{k: r[k] for k in ("id", "request", "expected", "got", "understood", "ask_back")}
                    for r in rows if not r["right"]],
          "rows": rows}
out = EVAL / f"approver_request_eval_{result['date']}.json"
out.write_text(json.dumps(result, indent=1, ensure_ascii=False, sort_keys=True, default=str) + "\n", encoding="utf-8",
               newline="\n")
print(f"Phase 2: exact {result['exact']} (EN {en}, AR {ar_}), ask-back {result['ask_back_recall']}, invented "
      f"{len(inv)}, model calls {calls} → {out.name}")
for w in result["wrong"]:
    print(f"  wrong {w['id']}: expected {norm(w['expected'])} got {norm(w['got'])} | {w['ask_back'] or ''}"[:400])
assert all(result["gate"].values()), result["gate"]
print(f"✅ Phase 2 validation passed: exact {result['exact']} ≥ {GATE} (EN {en}, AR {ar_} ≥ EN − {AR_MARGIN}), "
      "invented numbers 0")
DONE.append(2)

# %% Final Checkpoint
assert DONE == [1, 2], DONE
print("✅ Final Checkpoint: Phases 1–2 passed")
