"""Views evaluation (approver-additions plan D6, owner 2026-11-06): does the one structured call pick the right view?

Run:     uv run python dev/tools/run.py dev/checks/agents/Views_eval.py   (from the project root; real models)

Reads:   `Data/processed/agents/eval/views_golden.jsonl` (30 questions, 15 EN + 15 Egyptian AR, frozen 2026-11-06
         before the first real run; its SHA-256 is recorded in the results); the `tools` role's models (ADR-045; llm.py
         cache and quota: ≈ 30 requests the first time, cached after); PostgreSQL read-only through `finance_kpi`.
Writes:  `Data/processed/agents/eval/views_eval_<date>.json`.
Re-run:  safe (the replies are cached: a re-run scores the same choices).

Gate (D6, fixed before the run): the chosen view exactly right ≥ 0.90 over the 30 (a question naming no week is right
only when it asks back); RBAC leakage 0 — every chosen view fetched as an Operations employee is refused with no value.
"Exactly right" compares the kind, the week and every option after the catalogue's defaults (series as a set).
"""
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from pipelines.agents import roles as roles_mod, views  # noqa: E402
from pipelines.agents.roles import StructuredError  # noqa: E402
from pipelines.agents.tools import context, db  # noqa: E402
from pipelines.lib import common  # noqa: E402

common.load_env(ROOT)
GOLDEN = ROOT / "Data" / "processed" / "agents" / "eval" / "views_golden.jsonl"
GATE = 0.90
DEFAULTS = {"trend": {"series": ["billed_sdr", "budget_sdr"], "weeks": 13},
            "category": {"measure": "billed_sdr", "rows": "all", "compare_week": None},
            "aging": {"compare_week": None}, "customers": {"measure": "share_13w_pct"}}


def norm(c: dict) -> dict:
    out = {"kind": c["kind"], "week": c.get("week")}
    for opt, d in DEFAULTS[c["kind"]].items():
        v = c.get(opt)
        out[opt] = d if v is None else v
    if "series" in out:
        out["series"] = sorted(out["series"])
    return out


def right(expected: dict, got: dict | None) -> bool:
    if got is None:
        return False
    if expected["week"] is None:                    # D5: no week named → ask back, never guess
        return got.get("week") is None and got["kind"] == expected["kind"]
    return norm(got) == norm(expected)


# %% Run
raw = GOLDEN.read_bytes()
items = [json.loads(x) for x in raw.decode("utf-8").splitlines()]
assert len(items) == 30 and len({i["id"] for i in items}) == 30, "the frozen set changed shape"
people = db.fetch("SELECT e.employee_id, r.role_name, d.department_name FROM employees e JOIN roles r USING (role_id) "
                  "JOIN departments d USING (department_id) ORDER BY e.employee_id")
fin_mgr = context.load_user(next(p["employee_id"] for p in people
                                 if p["role_name"] == "manager" and p["department_name"] == "Finance"))
ops_emp = context.load_user(next(p["employee_id"] for p in people
                                 if p["role_name"] == "employee" and p["department_name"] == "Operations"))
roles = roles_mod.Roles()
rows, calls, cached, leaks, fetch_errors = [], 0, 0, [], []
for it in items:
    try:
        choice, usage = views.choose(it["question"], roles)
        got = choice.model_dump(exclude_none=True)
        calls, cached = calls + usage["calls"], cached + usage["cached"]
    except StructuredError as exc:
        got, choice = None, None
        calls += len(getattr(exc, "calls", []) or [1])
    ok = right(it["expected"], got)
    if choice is not None and choice.week is not None:
        try:
            views.fetch(ops_emp, choice)
            leaks.append(it["id"])                  # a value reached an employee without finance access
        except views.ViewUnavailable as exc:
            if exc.status != "not_permitted":
                leaks.append(it["id"])
        try:
            views.fetch(fin_mgr, choice)
        except views.ViewUnavailable as exc:
            fetch_errors.append((it["id"], str(exc)[:120]))
    rows.append({"id": it["id"], "lang": it["lang"], "question": it["question"], "expected": it["expected"],
                 "got": got, "right": ok})

# %% Score
def rate(sel):
    sel = list(sel)
    return round(sum(r["right"] for r in sel) / len(sel), 4) if sel else None


asks = [r for r in rows if r["expected"]["week"] is None]
result = {"date": date.today().isoformat(), "golden_sha256": hashlib.sha256(raw).hexdigest(),
          "exact": rate(rows), "exact_en": rate(r for r in rows if r["lang"] == "en"),
          "exact_ar": rate(r for r in rows if r["lang"] == "ar"), "ask_back_recall": rate(asks),
          "leakage": leaks, "fetch_errors": fetch_errors, "model_calls": calls, "cached": cached,
          "gate": {"exact_ge_0_90": (rate(rows) or 0) >= GATE, "leakage_0": not leaks},
          "wrong": [{k: r[k] for k in ("id", "question", "expected", "got")} for r in rows if not r["right"]],
          "rows": rows}
out = ROOT / "Data" / "processed" / "agents" / "eval" / f"views_eval_{result['date']}.json"
out.write_text(json.dumps(result, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
print(f"views: exact {result['exact']} (EN {result['exact_en']}, AR {result['exact_ar']}), ask-back "
      f"{result['ask_back_recall']}, leakage {len(leaks)}, fetch errors {len(fetch_errors)}, model calls {calls} "
      f"({cached} cached) → {out.name}")
for w in result["wrong"]:
    print(f"  wrong {w['id']}: expected {w['expected']} got {w['got']}")
assert not fetch_errors, fetch_errors
assert all(result["gate"].values()), result["gate"]
print(f"✅ Views evaluation passed: exact {result['exact']} ≥ {GATE} (EN {result['exact_en']}, AR "
      f"{result['exact_ar']}), ask-back {result['ask_back_recall']}, RBAC leakage 0")
