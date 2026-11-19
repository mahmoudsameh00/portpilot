"""The conversation-memory golden set (FastAPI plan §6a.4, P6m; ADR-065 to come): multi-turn dialogs in English and
Egyptian Arabic whose follow-ups the memory step must understand — frozen before `pipelines/agents/memory.py` exists.

Plan:    dev/history/archive/2026-11-05_FastAPI_plan.md §6a (approved 2026-11-03; owner A3 "intelligent memory").
Run:     uv run python dev/tools/run.py dev/build/agents/Memory_golden.py --review   the review page only (nothing frozen)
         uv run python dev/tools/run.py dev/build/agents/Memory_golden.py            freeze (first run) / assert
Reads:   PostgreSQL read-only: the askers' roles, the vessels and customers the dialogs name (they must exist).
Writes:  --review: dev/_scratch/memory_golden_review.md (git-ignored). Freeze: Data/processed/agents/eval/
         memory_golden.jsonl, once; later only through a recorded REFREEZE (old sha prefix + reason), as ADR-053.
Re-run:  safe.

A turn's expectation (the scorer, `Memory_check.py`, reads exactly these):
- `resolved_by`: the allowed ways — `none` (not a follow-up: routed as asked), `code` (the rules filled the gap),
  `model` (one guarded rewrite), `clarify` (the API asks back; no tool runs). A list = any of them.
- `entities`: what the standalone question must name, by kind (`vessel`, `report_week`, `customer`, `route`,
  `document`, `speed_kn`); a value `"previous"` = the one value of that kind the previous turn's cited evidence holds
  (known only at run time: e.g. "the customer with the largest overdue amount").
- `not_entities`: what must not be carried (e.g. a value of a refused part — RBAC per question, §6a.3).
- `status`: the allowed answer statuses (the supervisor's, or `clarify`).
- `upload` (dialog level): a fixture of `Data/processed/rag/eval/uploads/fixtures/` uploaded before the first turn.
Gates (§6a.4): leakage 0; numbers from this turn 100 %; invented entities 0; every `clarify` turn clarifies.
Primary: follow-up resolution ≥ 0.90 EN, AR ≥ EN − 0.10.

Phases
1. The askers (role / department as each dialog assumes) and every named vessel / customer exist.
2. The set's shape: ids unique, 2–4 turns, a first turn never a follow-up, kinds and languages covered.
3. --review: the page for the owner; else the freeze (first run) or the hash check.
"""
# %% Setup
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from pipelines.agents.tools import context, db  # noqa: E402

GOLDEN = ROOT / "Data" / "processed" / "agents" / "eval" / "memory_golden.jsonl"
REVIEW = ROOT / "dev" / "_scratch" / "memory_golden_review.md"
FROZEN = "212b1204b146aec1"        # frozen 2026-11-04 after the owner's review ("موافق، جمّده")
REVIEW_ONLY = "--review" in sys.argv
OPS, OPS2, FIN, FIN2, OPS_MGR = 12, 17, 13, 24, 2
ASKERS = {OPS: ("employee", "Operations"), OPS2: ("employee", "Operations"), FIN: ("employee", "Finance"),
          FIN2: ("employee", "Finance"), OPS_MGR: ("manager", "Operations")}
ANSWER = ["answered"]
FIRST = {"resolved_by": "none"}


def t(q, resolved_by="code", status=None, entities=None, not_entities=None):
    return {"q": q, "resolved_by": [resolved_by] if isinstance(resolved_by, str) else resolved_by,
            "status": status or (["clarify"] if resolved_by == "clarify" else ANSWER),
            "entities": entities or {}, "not_entities": not_entities or {}}


ITEMS = [
    # --- finance follow-ups (a Finance employee) ------------------------------------------------------------------
    {"id": "m01", "employee_id": FIN, "lang": "en", "kind": "finance", "turns": [
        t("How much did we bill in week 23 of 2025?", "none"),
        t("And week 24?", entities={"report_week": [24]}),
        t("Was that above or below budget?", entities={"report_week": [24]})]},
    {"id": "m02", "employee_id": FIN, "lang": "ar", "kind": "finance", "turns": [
        t("كام فوترنا في الأسبوع 23 من 2025؟", "none"),
        t("طب والأسبوع اللي بعده؟", entities={"report_week": [24]})]},
    {"id": "m03", "employee_id": FIN, "lang": "en", "kind": "finance", "turns": [
        t("What was DSO at the end of week 49 of 2025?", "none"),
        t("And the week before?", entities={"report_week": [48]}),
        t("Compare it with week 52.", entities={"report_week": [48, 52]})]},
    {"id": "m04", "employee_id": FIN2, "lang": "ar", "kind": "finance", "turns": [
        t("الـDSO كان كام في آخر الأسبوع 49 من 2025؟", "none"),
        t("والأسبوع اللي قبله؟", entities={"report_week": [48]})]},
    {"id": "m05", "employee_id": FIN, "lang": "en", "kind": "numbers", "turns": [
        t("How much did we bill in week 23 of 2025?", "none"),
        t("What is double that figure?", ["code", "model"], status=["answered", "not_in_data"],
          entities={"report_week": [23]})]},
    # --- operations follow-ups (an Operations employee) -----------------------------------------------------------
    {"id": "m06", "employee_id": OPS, "lang": "en", "kind": "operations", "turns": [
        t("Where is Special Voyager 001 now and what is its next port?", "none"),
        t("When will it arrive there?", entities={"vessel": [1]})]},
    {"id": "m07", "employee_id": OPS, "lang": "ar", "kind": "operations", "turns": [
        t("السفينة 21 فين دلوقتي؟", "none"),
        t("وهتوصل إمتى؟", entities={"vessel": [21]})]},
    {"id": "m08", "employee_id": OPS, "lang": "en", "kind": "operations", "turns": [
        t("Should vessel 21 go from Singapore to Rotterdam via Suez or the Cape?", "none"),
        t("And at 14 knots?", entities={"vessel": [21], "route": ["SGSIN-NLRTM"], "speed_kn": [14]})]},
    {"id": "m09", "employee_id": OPS2, "lang": "en", "kind": "operations", "turns": [
        t("Where is vessel 36 now?", "none"),
        t("And vessel 41?", entities={"vessel": [41]}),
        t("Which of the two arrives first?", entities={"vessel": [36, 41]})]},
    {"id": "m10", "employee_id": OPS, "lang": "ar", "kind": "operations", "turns": [
        t("السفينة 2 فاضلها كام ميل بحري لحد ما توصل؟", "none"),
        t("وبتحرق وقود قد إيه في اليوم؟", entities={"vessel": [2]})]},
    {"id": "m11", "employee_id": OPS_MGR, "lang": "en", "kind": "operations", "turns": [
        t("Which vessels have a high weather alert in the latest voyage watch?", "none"),
        t("Where is the first one now?", ["code", "model"], entities={"vessel": ["previous"]})]},
    # --- cross-product (a Finance employee: finance + level-1 operations) -----------------------------------------
    {"id": "m12", "employee_id": FIN, "lang": "en", "kind": "cross", "turns": [
        t("Which customer had the largest overdue amount at the end of week 52 of 2025?", "none"),
        t("Where are its vessels now?", ["code", "model"], entities={"customer": ["previous"]})]},
    {"id": "m13", "employee_id": FIN2, "lang": "ar", "kind": "cross", "turns": [
        t("مين العميل اللي عليه أكبر مبلغ متأخر في آخر الأسبوع 52 من 2025؟", "none"),
        t("وسفنه فين دلوقتي؟", ["code", "model"], entities={"customer": ["previous"]})]},
    # --- uploads (the asker's own document) -----------------------------------------------------------------------
    {"id": "m14", "employee_id": OPS, "lang": "en", "kind": "upload", "upload": "clean_D1.pdf", "turns": [
        t("What does my uploaded procedure say about the reefer pre-trip inspection?", "none"),
        t("And what about the electrical check?", ["code", "model"], entities={"document": ["ng_ops_prc_0042"]})]},
    {"id": "m15", "employee_id": OPS, "lang": "ar", "kind": "upload", "upload": "clean_D1.pdf", "turns": [
        t("المستند اللي رفعته بيقول إيه عن فحص الكهربا؟", "none"),
        t("وفيه إيه تاني بعد الخطوة دي؟", ["code", "model"], entities={"document": ["ng_ops_prc_0042"]})]},
    # --- RBAC across turns (an Operations employee may not read finance) ------------------------------------------
    {"id": "m16", "employee_id": OPS2, "lang": "en", "kind": "rbac", "turns": [
        t("Where is vessel 238 now?", "none"),
        t("And how many days past due is its overdue invoice at the end of week 52 of 2025?", ["none", "code"],
          status=["not_permitted", "partial"], entities={"vessel": [238]})]},
    {"id": "m17", "employee_id": OPS2, "lang": "en", "kind": "rbac", "turns": [
        t("Which customer had the largest overdue amount at the end of week 52 of 2025?", "none",
          status=["not_permitted"]),
        t("Where are its vessels now?", "clarify", not_entities={"customer": ["any"]})]},
    # --- not a follow-up, and follow-ups that must ask back -------------------------------------------------------
    {"id": "m18", "employee_id": FIN, "lang": "en", "kind": "independent", "turns": [
        t("How much did we bill in week 23 of 2025?", "none"),
        t("Where is Special Voyager 001 now?", "none", not_entities={"report_week": [23]})]},
    {"id": "m19", "employee_id": OPS, "lang": "en", "kind": "clarify", "turns": [
        t("Where are vessels 36 and 41 now?", "none"),
        t("When will it arrive?", "clarify")]},
    {"id": "m20", "employee_id": OPS, "lang": "ar", "kind": "clarify", "turns": [
        t("السفن 36 و41 فين دلوقتي؟", "none"),
        t("وهتوصل إمتى؟", "clarify")]},
    {"id": "m21", "employee_id": OPS2, "lang": "en", "kind": "clarify", "turns": [
        t("Where is vessel 36 now?", "none"),
        t("And the other one?", "clarify", not_entities={"vessel": ["any_other"]})]},
    {"id": "m22", "employee_id": FIN, "lang": "en", "kind": "clarify", "turns": [
        t("Which 3 customers had the largest overdue amounts at the end of week 52 of 2025?", "none"),
        t("Where are that customer's vessels now?", "clarify")]},
]


# %% Phase 1 — the askers and the named entities exist
for emp, want in ASKERS.items():
    u = context.load_user(emp)
    assert (u.role, u.department) == want, (emp, u)
vessels = {v for it in ITEMS for tr in it["turns"] for v in tr["entities"].get("vessel", []) if isinstance(v, int)}
found = {r["vessel_id"] for r in db.fetch("SELECT vessel_id FROM vessels WHERE vessel_id = ANY(%s)", (sorted(vessels),))}
assert found == vessels, sorted(vessels - found)
fixtures = ROOT / "Data" / "processed" / "rag" / "eval" / "uploads" / "fixtures"
assert all((fixtures / it["upload"]).exists() for it in ITEMS if "upload" in it)
print(f"✅ Phase 1 validation passed: {len(ASKERS)} askers as assumed; {len(vessels)} named vessels exist; the upload "
      "fixtures exist")


# %% Phase 2 — the set's shape
ids = [it["id"] for it in ITEMS]
assert len(ids) == len(set(ids)), "duplicate ids"
for it in ITEMS:
    assert 2 <= len(it["turns"]) <= 4 and it["turns"][0]["resolved_by"] == ["none"], it["id"]
    for tr in it["turns"]:
        assert set(tr["resolved_by"]) <= {"none", "code", "model", "clarify"}, it["id"]
        assert set(tr["entities"]) | set(tr["not_entities"]) <= {"vessel", "report_week", "customer", "route",
                                                                  "document", "speed_kn"}, it["id"]
        assert ("clarify" in tr["resolved_by"]) == (tr["status"] == ["clarify"]), it["id"]
langs, kinds = Counter(it["lang"] for it in ITEMS), Counter(it["kind"] for it in ITEMS)
follow_ups = [tr for it in ITEMS for tr in it["turns"][1:]]
clarify = sum(tr["resolved_by"] == ["clarify"] for tr in follow_ups)
assert langs["ar"] >= 7 and set(kinds) == {"finance", "numbers", "operations", "cross", "upload", "rbac",
                                           "independent", "clarify"}, (langs, kinds)
print(f"✅ Phase 2 validation passed: {len(ITEMS)} dialogs, {len(follow_ups)} follow-ups ({clarify} must clarify), "
      f"languages {dict(langs)}, kinds {dict(kinds)}")


# %% Phase 3 — the review page, or the freeze
text = "".join(json.dumps(it, ensure_ascii=False, sort_keys=True) + "\n" for it in ITEMS)
sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
if REVIEW_ONLY:
    lines = [f"# Memory golden set — review (not frozen; sha {sha[:16]}…)", "",
             "| id | asker | lang | kind | turn | question | resolved by | must name | must not carry | status |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for it in ITEMS:
        role = "/".join(ASKERS[it["employee_id"]])
        for i, tr in enumerate(it["turns"], 1):
            up = f" (upload {it['upload']})" if i == 1 and "upload" in it else ""
            lines.append(f"| {it['id']} | {it['employee_id']} {role} | {it['lang']} | {it['kind']} | {i} | "
                         f"{tr['q']}{up} | {', '.join(tr['resolved_by'])} | "
                         f"{json.dumps(tr['entities'], ensure_ascii=False) if tr['entities'] else ''} | "
                         f"{json.dumps(tr['not_entities'], ensure_ascii=False) if tr['not_entities'] else ''} | "
                         f"{', '.join(tr['status'])} |")
    REVIEW.parent.mkdir(parents=True, exist_ok=True)
    REVIEW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"✅ Phase 3 validation passed: review page {REVIEW.relative_to(ROOT).as_posix()} (nothing frozen)")
else:
    assert FROZEN != "PENDING", "freeze only after the owner's review: set FROZEN to the reviewed sha prefix"
    if not GOLDEN.exists():
        GOLDEN.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {GOLDEN.name} (the freeze)")
    on_disk = GOLDEN.read_text(encoding="utf-8")
    assert hashlib.sha256(on_disk.encode("utf-8")).hexdigest().startswith(FROZEN) and on_disk == text, sha[:16]
    print(f"✅ Phase 3 validation passed: the frozen set unchanged (sha {sha[:16]}…)")
