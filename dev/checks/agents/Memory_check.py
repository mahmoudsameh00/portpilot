"""Conversation-memory check (FastAPI plan §6a.3 / §6a.4, P6m): the rules of `pipelines/agents/memory.py` on the
frozen golden set, the frame builder, the masking, the guard on a model rewrite — and, with EVAL_REAL_MODELS=1, the
dialogs end to end through the API on the real models.

Plan:    dev/history/archive/2026-11-05_FastAPI_plan.md §6a (approved 2026-11-03; the golden set frozen 2026-11-04 after the owner's review).
Run:     uv run python dev/tools/run.py dev/checks/agents/Memory_check.py                         (Phases 1–3, 0 calls)
         $env:EVAL_REAL_MODELS = '1'; uv run python dev/tools/run.py dev/checks/agents/Memory_check.py   (+ Phase 4)
Reads:   Data/processed/agents/eval/memory_golden.jsonl (hash-asserted); Phase 4: the databases and the real models.
Writes:  nothing (Phases 1–3); Phase 4: the results file, the llm cache, rows it deletes again.
Re-run:  safe.

Phases
1. `frame_of` on hand-made states: the bound rows only (not every row the tool returned), the cited evidence when
   nothing is bound, the asker's upload as the document, a route advice's route, nothing from a refused part;
   `mask` replaces every slot.
2. `resolve` on the 22 frozen dialogs, each first turn's frame written here by hand (what its cited rows hold): every
   follow-up resolved the allowed way, naming every expected entity (in the standalone text for ids, weeks and
   speeds), carrying no forbidden one; every `clarify` turn clarifies; nothing invented.
2b. The owner's web dialogs of 2026-11-16 (each failed before the fix): a compare keeps the previous subject, a
   pronoun bound to its noun ("الأسبوع ده") carries that kind only, asking back names the options and offers "all of
   them", a reply completes the pending question, Arabic pronouns are whole words, an owned possessive is not a
   follow-up, "؟" does not make an English question Arabic.
3. The model rewrite's guard: an invented vessel → clarify, a number the user never wrote → clarify, a clean rewrite
   → `model`; `needs_clarification` → clarify.
4. (EVAL_REAL_MODELS=1) the 22 dialogs through the API (TestClient, the real models, EVAL_REPEATS runs — default 2 —
   each on its own llm cache folder `llm_cache/memory_r<k>/`, so a repeat is a fresh set of calls; tokens for the five
   askers written by the owner account; the upload fixtures uploaded first): the §6a.4 gates in every run — leakage 0
   (no finance evidence for an Operations asker, no forbidden entity carried), numbers from this turn 100 % (every
   answered turn passed the supervisor's code check), invented entities 0, every clarify turn clarifies — and the
   primary, follow-up resolution ≥ 0.90 EN, AR ≥ EN − 0.10; results `Data/processed/agents/eval/memory_eval_<date>.json`;
   everything the runs created deleted (threads, conversations, audit rows, tokens, temporary logins).
Final Checkpoint.
"""
# %% Setup
import hashlib
import json
import os
import secrets
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from pipelines.agents import memory  # noqa: E402

GOLDEN = ROOT / "Data" / "processed" / "agents" / "eval" / "memory_golden.jsonl"
FROZEN = "212b1204b146aec1"
OPS_EMPLOYEES = (12, 17)
DONE: list[float] = []
text = GOLDEN.read_text(encoding="utf-8")
assert hashlib.sha256(text.encode("utf-8")).hexdigest().startswith(FROZEN), "the frozen set changed"
GOLD = [json.loads(line) for line in text.splitlines()]


# %% Phase 1 — the frame builder and the mask
state = {"evidence": {"kpi.c": {"tool": "finance_kpi", "rows": [{"customer_id": 7, "report_week": 52},
                                                                  {"customer_id": 9, "report_week": 52}]},
                      "doc.1": {"tool": "search_documents", "rows": [
                          {"document_id": "lpi_2025", "lane": None},
                          {"document_id": "ng_ops_prc_0042", "lane": "upload"}]},
                      "route.1": {"tool": "route_advice", "rows": [{"route": "advice"}],
                                  "source": {"filter": "SGSIN → NLRTM, vessel_id = 21, as of 2026-09-13"}}},
         "bound": [{"eid": "kpi.c", "row": 0, "field": "overdue_sdr"}],
         "answer": {"evidence_ids": ["kpi.c", "doc.1"]}}
f = memory.frame_of(state, "Which customer had the largest overdue amount at the end of week 52 of 2025?")
assert f == {"report_week": [52], "customer": [7], "document": ["ng_ops_prc_0042"], "route": ["SGSIN-NLRTM"],
             "vessel": [21]}, f
unbound = memory.frame_of({**state, "bound": []}, "Which customers?")
assert unbound["customer"] == [7, 9], unbound                   # nothing bound: the cited evidence's rows
refused = memory.frame_of({"evidence": {}, "bound": [], "answer": {"evidence_ids": []}}, "Which customer had the "
                          "largest overdue amount?")
assert refused == {}, refused                                     # a refused part left no rows
assert memory.mask("Billed {kpi.weekly:billed_sdr|money} in week 23 ({kpi.weekly:invoices})") == \
    "Billed ⟨n⟩ in week 23 (⟨n⟩)"
DONE.append(1)
print("✅ Phase 1 validation passed: the frame = the bound rows (not every row), the cited evidence when nothing is "
      "bound, the upload as the document, the route; nothing from a refused part; every slot masked")


# %% Phase 2 — the frozen dialogs through the rules
FIRST_FRAMES = {   # what each first turn's cited rows hold (by hand; the real run builds them from the evidence)
    "m01": {"report_week": [23]}, "m02": {"report_week": [23]}, "m03": {"report_week": [49]},
    "m04": {"report_week": [49]}, "m05": {"report_week": [23]}, "m06": {"vessel": [1]}, "m07": {"vessel": [21]},
    "m08": {"vessel": [21], "route": ["SGSIN-NLRTM"]}, "m09": {"vessel": [36]}, "m10": {"vessel": [2]},
    "m11": {"vessel": [301, 145, 77]}, "m12": {"customer": [7], "report_week": [52]},
    "m13": {"customer": [7], "report_week": [52]}, "m14": {"document": ["ng_ops_prc_0042"]},
    "m15": {"document": ["ng_ops_prc_0042"]}, "m16": {"vessel": [238]}, "m17": {}, "m18": {"report_week": [23]},
    "m19": {"vessel": [36, 41]}, "m20": {"vessel": [36, 41]}, "m21": {"vessel": [36]},
    "m22": {"customer": [3, 7, 9], "report_week": [52]}}
TEXT_KINDS = ("vessel", "report_week", "customer", "speed_kn")
wrong, by_lang, counts = [], {"en": [0, 0], "ar": [0, 0]}, {"none": 0, "code": 0, "model": 0, "clarify": 0}
for it in GOLD:
    first = it["turns"][0]
    r0 = memory.resolve(first["q"], it["lang"], [])
    assert r0.by == "none", (it["id"], r0)
    # a refused first question leaves no history (the API skips not_permitted turns), like a clarify
    history = [] if first["status"] == ["not_permitted"] else [memory.Turn(first["q"], first["q"],
                                                                         FIRST_FRAMES[it["id"]])]
    for i, tr in enumerate(it["turns"][1:], 2):
        r = memory.resolve(tr["q"], it["lang"], history)
        counts[r.by] += 1
        prev = history[-1].frame if history else {}
        ok = r.by in tr["resolved_by"]
        for kind, vals in tr["entities"].items():
            want = [prev.get(kind, [None])[0] if v == "previous" else v for v in vals]
            ok &= all(v in r.used.get(kind, []) for v in want)
            if kind in TEXT_KINDS and r.by != "clarify":
                ok &= all(str(int(v) if isinstance(v, float) and v.is_integer() else v) in r.standalone
                          for v in want)
        for kind, vals in tr["not_entities"].items():
            got = r.used.get(kind, [])
            if vals == ["any"]:
                ok &= not got
            elif vals == ["any_other"]:
                ok &= set(got) <= set(prev.get(kind, []))
            else:
                ok &= not set(got) & set(vals)
        relative = bool(memory.NEXT_WEEK.search(tr["q"]) or memory.PREV_WEEK.search(tr["q"]))
        derived = {w + d for w in prev.get("report_week", []) for d in (1, -1)} if relative else set()
        invented = [(k, v) for k, vs in r.used.items() for v in vs
                    if not any(v in t.frame.get(k, []) for t in history) and v not in
                    memory.own_entities(tr["q"]).get(k, []) and not (k == "report_week" and v in derived)]
        ok &= not invented
        by_lang[it["lang"]][0] += ok
        by_lang[it["lang"]][1] += 1
        if not ok:
            wrong.append((it["id"], i, r.by, r.used, r.standalone[:90] or r.clarify))
        history.append(memory.Turn(tr["q"], r.standalone or tr["q"], r.used if r.by != "clarify" else {}))
for w in wrong:
    print("  wrong:", w)
acc = {k: round(a / n, 3) for k, (a, n) in by_lang.items()}
assert not wrong, f"{len(wrong)} follow-up(s) resolved wrongly"
DONE.append(2)
print(f"✅ Phase 2 validation passed: {sum(n for _, n in by_lang.values())} follow-ups of the frozen set resolved as "
      f"expected by the rules (EN {acc['en']}, AR {acc['ar']}); ways {counts}; nothing invented, nothing refused "
      f"carried, every clarify turn clarifies")


# %% Phase 2b — the owner's web dialogs of 2026-11-16 (regressions: each one failed before the fix)
from pipelines.agents.graphs.supervisor import detect_lang  # noqa: E402

T = memory.Turn
q1 = "What was collected revenue in week 17 versus the amount due?"
r = memory.resolve("And how does that compare with week 16", "en", [T(q1, q1, {"report_week": [17]})])
assert r.by == "code" and r.used["report_week"] == [17, 16], r                    # the subject kept, both weeks
assert r.standalone.startswith("What was collected revenue in week 17 and week 16 versus the amount due?"), r
qa = "إيه أكتر 3 عملاء علينا فلوس متأخرة"
fa = {"report_week": [52], "customer": [15, 9, 10],
      "labels": {"customer:15": "Belanor Tankers", "customer:9": "Talomar Shipping", "customer:10": "Levavia Tankers"}}
ha = [T(qa, qa, fa)]
r = memory.resolve("طب والمتأخرات زادت ولا قلّت الأسبوع ده", "ar", ha)
assert r.by == "code" and r.used == {"report_week": [52]}, r                    # "الأسبوع ده" = the week, no customer
r = memory.resolve("طب والعميل ده متأخراته زادت؟", "ar", ha)                       # a customer pronoun: ask back, by name
assert r.by == "clarify" and r.kind == "customer" and r.options == [15, 9, 10], r
assert "Belanor Tankers (15)" in (r.clarify or "") and "كلهم" in (r.clarify or ""), r.clarify
pend = {"kind": r.kind, "options": r.options, "labels": r.labels, "question": "طب والعميل ده متأخراته زادت؟"}
replies = {"قصدي في العموم": {"report_week": [52]}, "العميل 9": {"report_week": [52], "customer": [9]},
           "Belanor": {"report_week": [52], "customer": [15]}, "التاني": {"report_week": [52], "customer": [9]},
           "15": {"report_week": [52], "customer": [15]}}
for reply, used in replies.items():                                             # the reply completes the pending one
    a = memory.answer_clarify(reply, pend, "ar", ha)
    assert a is not None and a.by == "code" and a.used == used, (reply, a)
assert "كل العملاء" in (memory.answer_clarify("قصدي في العموم", pend, "ar", ha) or r).standalone
again = memory.answer_clarify("مش فاهم", pend, "ar", ha)
assert again is not None and again.by == "clarify", again                       # picks nothing → asked back again
assert memory.answer_clarify("What was billed in week 30 of 2025?", pend, "ar", ha) is None   # a new question
assert not memory.is_follow_up("قصدي في العموم") and not memory.is_follow_up("هدية")   # "دي" inside a word
assert memory.is_follow_up("السفينة دي فين") and memory.is_follow_up("وده كان أعلى من الميزانية؟")
q5 = "Which vessels are anchored waiting near their destination?"
assert not memory.is_follow_up(q5) and memory.resolve(q5, "en", []).by == "none"   # "their" = the vessels named
assert memory.is_follow_up("What is their ETA?")                                # no owner named → a follow-up
assert detect_lang(q5[:-1] + "؟") == "en" and detect_lang("كام فوترنا؟") == "ar"    # Arabic letters decide
DONE.append(2.5)
print("✅ Phase 2b validation passed: the 2026-11-16 web dialogs — a compare keeps its subject, 'الأسبوع ده' carries "
      "the week only, asking back names the options and offers 'all of them', a reply completes the pending question "
      "(general / id / name / ordinal), Arabic pronouns are whole words, a possessive owned in the question is not a "
      "follow-up, '؟' does not make English Arabic")


# %% Phase 3 — the model rewrite's guard
hist = [memory.Turn("Where is vessel 36 now?", "Where is vessel 36 now?", {"vessel": [36]})]
plain = "Like before, but how far is that from port?"


def fake(text: str, clarify: bool = False):
    return lambda q, h: memory.StandaloneQuestion(text=text, needs_clarification=clarify)


cases = {"invented vessel": (fake("How far is vessel 99 from port?"), "clarify"),
         "a new number": (fake("How far is vessel 36 from port, in 12 hours?"), "clarify"),
         "asks back": (fake("", True), "clarify"),
         "clean": (fake("How far is vessel 36 from its next port?"), "model")}
for name, (fn, want) in cases.items():
    # a follow-up the rules leave to the model: no lead-in value, no carried kind (the frame is emptied for the rules)
    r = memory._model(plain, "en", hist, fn)
    assert r.by == want, (name, r)
DONE.append(3)
print("✅ Phase 3 validation passed: a rewrite naming an invented vessel or adding a number → clarify; "
      "needs_clarification → clarify; a clean rewrite → model")


# %% Phase 4 — the dialogs through the API on the real models (EVAL_REAL_MODELS=1)
REAL = os.environ.get("EVAL_REAL_MODELS") == "1"
REPEATS = int(os.environ.get("EVAL_REPEATS", "2"))
if not REAL:
    print("Phase 4 skipped: set EVAL_REAL_MODELS=1 (≈ 120–140 flash-lite requests a run)")
else:
    from fastapi.testclient import TestClient

    from pipelines.agents import checkpointer, llm, roles
    from pipelines.api import app as app_mod
    from pipelines.lib.common import load_env

    load_env(ROOT)
    E = os.environ
    B = app_mod.BASE
    FIX = ROOT / "Data" / "processed" / "rag" / "eval" / "uploads" / "fixtures"
    FINANCE_TOOLS = {"finance_kpi", "invoice_audit"}
    started_at = datetime.now(timezone.utc)

    def owner():
        return psycopg.connect(host=E["PGHOST"], port=E["PGPORT"], dbname=E["PGDATABASE"], user=E["PGUSER"],
                               password=E["PGPASSWORD"], autocommit=True, row_factory=dict_row)

    askers = sorted({it["employee_id"] for it in GOLD})
    tokens, temp_logins, created_threads, convs = {}, [], [], []
    with owner() as oc:
        have = {r["employee_id"] for r in oc.execute("SELECT employee_id FROM api.logins WHERE employee_id = ANY(%s)",
                                                     (askers,)).fetchall()}
        for emp in askers:
            if emp not in have:          # a temporary login, never usable for a sign-in (no scrypt hash of anything)
                oc.execute("INSERT INTO api.logins (employee_id, password_hash) VALUES (%s, 'scrypt$memory$check$-$-$-')",
                           (emp,))
                temp_logins.append(emp)
            tok = secrets.token_urlsafe(32)
            oc.execute("INSERT INTO api.tokens (token_sha256, employee_id, expires_at) VALUES (%s, %s, now() + "
                       "interval '3 hours')", (hashlib.sha256(tok.encode()).digest(), emp))
            tokens[emp] = tok

    def turn_rows(conv: str) -> list[dict]:
        with owner() as oc:
            return oc.execute("SELECT turn_no, resolved_by, standalone_question, frame, status, thread_id FROM "
                              "api.conversation_turns WHERE conversation_id::text = %s ORDER BY turn_no",
                              (conv,)).fetchall()

    def run_dialogs(k: int) -> list[dict]:
        cache = llm.CACHE_DIR / f"memory_r{k}"
        quota = llm.QuotaState(llm.CACHE_DIR)
        app = app_mod.create_app(roles_factory=lambda: roles.Roles(cache_dir=cache, quota=quota), access_log=None)
        out = []
        with TestClient(app, raise_server_exceptions=False) as client:
            for it in GOLD:
                h = {"Authorization": f"Bearer {tokens[it['employee_id']]}"}
                conv = client.post(f"{B}/conversations", headers=h).json()["conversation_id"]
                convs.append(conv)
                if "upload" in it:
                    up = client.post(f"{B}/conversations/{conv}/uploads", headers=h, timeout=300,
                                     files={"file": (it["upload"], (FIX / it["upload"]).read_bytes())})
                    assert up.status_code == 201, up.text[:200]
                prev_frame: dict = {}
                frames_so_far: list[dict] = []
                for i, tr in enumerate(it["turns"], 1):
                    acc = client.post(f"{B}/conversations/{conv}/questions", json={"question": tr["q"]}, headers=h)
                    assert acc.status_code == 202, acc.text[:300]
                    created_threads.append(acc.json()["thread_id"])
                    ev, cur = [], {}
                    with client.stream("GET", acc.json()["events_url"], headers=h) as s:
                        for line in s.iter_lines():
                            if line.startswith("event:"):
                                cur["event"] = line[6:].strip()
                            elif line.startswith("data:"):
                                cur["data"] = json.loads(line[5:].strip())
                            elif not line and cur:
                                ev.append((cur["event"], cur["data"]))
                                cur = {}
                    ans = next((d for e, d in ev if e == "answer"), None)
                    failed = next((d for e, d in ev if e == "failed"), None)
                    und = next((d for e, d in ev if e == "understood"), None)
                    row = turn_rows(conv)[-1]
                    by = row["resolved_by"]
                    used = (und or {}).get("used_entities") or (memory.own_entities(tr["q"]) if by == "none" else {})
                    status = (ans or {}).get("status") or ("failed" if failed else None)
                    tools = {v["tool"] for v in ((ans or {}).get("evidence") or {}).values()}
                    rec = {"id": it["id"], "lang": it["lang"], "turn": i, "q": tr["q"], "by": by, "used": used,
                           "standalone": (und or {}).get("standalone_question"), "status": status,
                           "tools": sorted(tools), "problems": (ans or {}).get("problems") or [],
                           "model_calls": (ans or {}).get("model_calls"), "failed": failed}
                    if i > 1:
                        ok = by in tr["resolved_by"]
                        for kind, vals in tr["entities"].items():
                            want = [(prev_frame.get(kind) or [None])[0] if v == "previous" else v for v in vals]
                            ok &= all(v in used.get(kind, []) for v in want)
                        rec["resolved_ok"] = bool(ok)
                    # an Operations *employee* (12, 17) may not read the finance views; the manager (2) may (ADR-006)
                    leak = bool(tools & FINANCE_TOOLS) and it["employee_id"] in OPS_EMPLOYEES
                    for kind, vals in tr["not_entities"].items():
                        got = used.get(kind, [])
                        leak |= bool(got) if vals == ["any"] else False
                    rec["leak"] = leak
                    derived = {w + d for f in frames_so_far for w in f.get("report_week", []) for d in (1, -1)}
                    rec["invented"] = [(kk, v) for kk, vs in used.items() for v in vs
                                       if not any(v in f.get(kk, []) for f in frames_so_far)
                                       and v not in memory.own_entities(tr["q"]).get(kk, [])
                                       and not (kk == "report_week" and v in derived)]
                    rec["clarify_ok"] = (status == "clarify") if tr["resolved_by"] == ["clarify"] else None
                    rec["numbers_ok"] = status not in ("answered", "partial") or not rec["problems"]
                    rec["status_ok"] = status in tr["status"]
                    prev_frame = row["frame"] or {}
                    frames_so_far.append(prev_frame)
                    out.append(rec)
                    print(f"  r{k} {it['id']}.{i} {it['lang']}: {by:<7} {status} "
                          f"{'' if i == 1 else ('✓' if rec.get('resolved_ok') else '✗')} {(rec['standalone'] or '')[:70]}")
        return out

    def summarise(recs: list[dict]) -> dict:
        fu = [r for r in recs if r["turn"] > 1]
        res = {lang: round(sum(r["resolved_ok"] for r in fu if r["lang"] == lang) /
                           max(1, sum(r["lang"] == lang for r in fu)), 4) for lang in ("en", "ar")}
        gates = {"leakage_0": not any(r["leak"] for r in recs), "invented_0": not any(r["invented"] for r in recs),
                 "numbers_from_this_turn": all(r["numbers_ok"] for r in recs),
                 "clarify_all": all(r["clarify_ok"] for r in recs if r["clarify_ok"] is not None),
                 "no_failed_run": not any(r["failed"] for r in recs)}
        primary = {"resolution": res, "en_ok": res["en"] >= 0.90, "ar_ok": res["ar"] >= res["en"] - 0.10,
                   "status_ok": round(sum(r["status_ok"] for r in recs) / len(recs), 4)}
        return {"gates": gates, "primary": primary}

    runs_out, results = [], {}
    try:
        for k in range(1, REPEATS + 1):
            recs = run_dialogs(k)
            s = summarise(recs)
            runs_out.append({"run": k, "summary": s, "turns": recs})
            print(f"  run {k}: gates {s['gates']} | primary {s['primary']}")
    finally:
        saver = checkpointer.saver()
        for t in created_threads:
            saver.delete_thread(t)
        with owner() as oc:
            oc.execute("DELETE FROM api.audit_log WHERE at >= %s AND employee_id = ANY(%s)", (started_at, askers))
            oc.execute("DELETE FROM api.conversations WHERE conversation_id::text = ANY(%s)", (convs,))
            oc.execute("DELETE FROM api.tokens WHERE token_sha256 = ANY(%s)",
                       ([hashlib.sha256(t.encode()).digest() for t in tokens.values()],))
            oc.execute("DELETE FROM api.logins WHERE employee_id = ANY(%s)", (temp_logins,))
        print(f"clean-up: {len(created_threads)} thread(s), {len(convs)} conversation(s), {len(tokens)} token(s), "
              f"{len(temp_logins)} temporary login(s) deleted")
    path = ROOT / "Data" / "processed" / "agents" / "eval" / f"memory_eval_{date.today().isoformat()}.json"
    path.write_text(json.dumps({"set_sha": FROZEN, "date": date.today().isoformat(), "runs": runs_out},
                               ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    held = all(all(r["summary"]["gates"].values()) and r["summary"]["primary"]["en_ok"] and
               r["summary"]["primary"]["ar_ok"] for r in runs_out)
    print(f"results: {path.relative_to(ROOT).as_posix()}")
    assert len(runs_out) == REPEATS and held, [r["summary"] for r in runs_out]
    DONE.append(4)
    print(f"✅ Phase 4 validation passed: {REPEATS} real runs, every gate held and the resolution primary met in each "
          f"({[r['summary']['primary']['resolution'] for r in runs_out]})")


# %% Final Checkpoint
PHASES = {1: "frame + mask", 2: "the frozen dialogs (rules)", 2.5: "the 2026-11-16 web dialogs", 3: "the rewrite guard", 4: "real models via the API"}
pending = [f"{k} {v}" for k, v in PHASES.items() if k not in DONE]
print(f"Final Checkpoint: done {DONE}; pending: {pending}")
print(f"✅ Final Checkpoint: {len(DONE)} / {len(PHASES)} phases passed")
