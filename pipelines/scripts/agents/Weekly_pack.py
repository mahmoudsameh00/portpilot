"""Run the Weekly Finance Pack for one report week, and decide on it (Agents plan §5b, P5-4 / P5-5).

Commands (from the project root):
    uv run python pipelines/scripts/agents/Weekly_pack.py run --week 23 --as 12
        start a new attempt of week 23 as employee 12 (a Finance manager: the pack's run identity); it stops at the
        approval (prints the draft with bullet numbers and the path of the PPTX preview in reports/_drafts/) or at a
        stated stop status; approval saves an immutable four-file pack under reports/2025-W23/_publications/ and
        atomically selects it with publication.json. The CLI/API expose its resolved download path.
    uv run python pipelines/scripts/agents/Weekly_pack.py show --thread weekly_pack:live:2025-W23:1
        where a thread stands, and the draft waiting for a decision
    uv run python pipelines/scripts/agents/Weekly_pack.py resume --thread weekly_pack:live:2025-W23:1 --as 12 \
        --decision approve | reject | edit --draft-sha <version-from-show> [--edits edits.json] [--comment "…"]
        decide as employee 12 (a Finance manager or the CEO, checked in PostgreSQL); edits.json =
        [{"bullet": 3, "text": "…"}] — an edit goes back through the Validator and waits again
    uv run python pipelines/scripts/agents/Weekly_pack.py resume --thread … --as 12 --request "<words>" [--yes]
        the manager's request in words (approver-request plan): prints what it understood and the steps; --yes
        applies them (a revise first, then the wording on the new draft), then the pack waits again
    uv run python pipelines/scripts/agents/Weekly_pack.py list [--week 23]
        the threads in agent_state
    uv run python pipelines/scripts/agents/Weekly_pack.py scheduled [--as 12]
        what Windows Task Scheduler runs (Phase 8, §5e): the next week of the replay as the scheduled identity
        (PACK_RUN_AS in .env, or --as), or wait while a pack waits for approval, or resume a pack stopped mid-run;
        then the retention; one line in reports/_log/scheduled.jsonl; a Windows toast when a pack waits
    uv run python pipelines/scripts/agents/Weekly_pack.py prune [--dry-run]
        (also the route-advice threads `route_advice:…`, Agents plan §6b P10-3, by the same 30-day rule)
        retention by hand: archive, then delete ended threads older than 30 days (never a pending one)
    uv run python pipelines/scripts/agents/Weekly_pack.py report
        G5: approve / edit / reject counts and the edited slides of every decided pack

Reads:   PostgreSQL (read-only tools; the checkpoints through ports_agent), the LLM APIs of ADR-045 (cached), the
         external tools (cached). Writes: checkpoints in agent_state; on approval reports/2025-W<ww>/ (git-ignored);
         reports/_log/ (scheduled.jsonl, threads_archive.jsonl).
Re-run:  `run` always starts a new attempt (a new thread); `resume` continues one; `scheduled` never starts a second
         pack while one waits (§5e P8-1). The evaluation copy (`dataset="test"`) is not offered here: only the
         evaluation harness sets it (ADR-049).
Exit:    0 done (including "wait" / "done"); 1 the pack raised (the thread waits at its checkpoint); 2 the database
         did not answer within PROBE_WAIT_MIN; 3 the scheduled identity is not a Finance manager.
"""
import argparse
import json
import logging
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from langgraph.types import Command  # noqa: E402

from pipelines.agents import approver_request, checkpointer, locks, monitoring, publications, roles, scheduling, tracing  # noqa: E402
from pipelines.agents.graphs import weekly_pack as wp  # noqa: E402
from pipelines.agents.tools import context, db  # noqa: E402
from pipelines.lib.common import load_env, redact  # noqa: E402

PREFIX = scheduling.LIVE_PREFIX
REPORTS = ROOT / "reports"
LOG = REPORTS / scheduling.LOG_DIR
PROBE_WAIT_MIN, PROBE_EVERY_S = 30, 60      # Docker Desktop starts after logon: the firing waits for PostgreSQL
LOCK_STALE_H = 2


def threads(week: int | None = None) -> list[str]:
    return scheduling.thread_ids(checkpointer.pool(), f"{PREFIX}{week:02d}:" if week else PREFIX)


def next_attempt(week: int) -> str:
    used = [int(t.rsplit(":", 1)[1]) for t in threads(week) if t.rsplit(":", 1)[1].isdigit()]
    return f"{PREFIX}{week:02d}:{max(used, default=0) + 1}"


def probe() -> str | None:
    """None when both logins answer (the checkpointer's and the read-only tools'), else the last error."""
    deadline, err = time.monotonic() + PROBE_WAIT_MIN * 60, None
    while True:
        try:
            with checkpointer.pool().connection() as conn:
                conn.execute("SELECT 1")
            db.fetch("SELECT 1 AS ok")
            return None
        except Exception as exc:  # noqa: BLE001 — any failure to reach the database means "not yet"
            err = f"{type(exc).__name__}: {exc}"
            checkpointer.close()
            db.close()
        if time.monotonic() >= deadline:
            return err
        time.sleep(PROBE_EVERY_S)


def scheduled(employee: int | None) -> int:
    LOG.mkdir(parents=True, exist_ok=True)
    rec = {"at": scheduling.now_utc().isoformat(timespec="seconds"), "cmd": "scheduled"}
    lock = LOG / "scheduled.lock"
    if lock.exists() and time.time() - lock.stat().st_mtime < LOCK_STALE_H * 3600:
        rec["skipped"] = "another firing is running (lock)"
        scheduling.append_jsonl(LOG / "scheduled.jsonl", rec)
        print(rec["skipped"])
        return 0
    lock.write_text(str(os.getpid()), encoding="utf-8")
    code = 0
    try:
        err = probe()
        if err:
            rec["error"], code = f"database unreachable: {redact(err)[:300]}", 2
            return code
        load_env(ROOT)
        run_as = employee or int(os.environ.get("PACK_RUN_AS") or 0)
        try:
            user = context.load_user(run_as) if run_as else None
        except PermissionError:               # an unknown employee id
            user = None
        if not scheduling.allowed_run_as(user):
            rec["error"], code = f"scheduled identity {run_as or 'unset'} is not a Finance manager (PACK_RUN_AS)", 3
            return code
        rec["run_as"] = run_as
        rec.update(scheduling.fire(graph(), checkpointer.saver(), checkpointer.pool(), user, REPORTS,
                                   tracer=scheduled_tracer, route_graph=route_graph(), ask_graph=ask_graph(),
                                   arrival_graph=arrival_graph()))
        rec["operational"] = scheduling.operational_outcome(rec, "weekly_pack")
        code = rec["operational"]["exit"]
        if code:
            logging.getLogger(__name__).warning("Scheduled weekly pack needs attention: %s (%s)",
                                                rec["operational"]["reason"], rec.get("result"))
    except Exception as exc:  # noqa: BLE001 — logged for the owner; the thread (if any) waits at its checkpoint
        rec["error"], code = redact(f"{type(exc).__name__}: {exc}")[:600], 1
        rec["trace"] = redact(traceback.format_exc(limit=3))[-1200:]
        monitoring.capture(exc)
    finally:
        rec["exit"] = code
        scheduling.append_jsonl(LOG / "scheduled.jsonl", rec)
        lock.unlink(missing_ok=True)
        print(json.dumps({k: v for k, v in rec.items() if k != "trace"}, ensure_ascii=False, default=str, indent=1))
    return code


def scheduled_tracer(thread_id: str, run_as: int | None):
    """The firing's graph run: a LangSmith trace, and the same thread id as a Sentry tag (the link between the two)."""
    monitoring.tag(thread_id=thread_id, run_as=run_as)
    return tracing.trace(thread_id, entry="scheduled", run_as=run_as, launched_by="task_scheduler")


def graph():
    return wp.build_graph(roles.Roles(), checkpointer.saver())


def route_graph():
    """The route_advice graph on the same checkpointer, only to read and prune its threads (no model is called)."""
    from pipelines.agents.graphs import route_advice
    return route_advice.build_graph(None, checkpointer.saver())


def arrival_graph():
    """The arrival_advice graph on the same checkpointer, only to read and prune its threads (JIT arrival plan)."""
    from pipelines.agents.graphs import arrival_advice
    return arrival_advice.build_graph(None, checkpointer.saver())


def ask_graph():
    """The supervisor on the same checkpointer, only to read and prune its question threads (no model is called;
    Agents plan §6d S4)."""
    from pipelines.agents.graphs import supervisor
    return supervisor.build_graph(None, checkpointer.saver())


def show(g, cfg) -> None:
    snap = g.get_state(cfg)
    st = snap.values
    print(f"thread {cfg['configurable']['thread_id']} | status {st.get('status')} | next {list(snap.next) or 'END'}")
    for r in (st.get("readiness") or {}).get("reasons", []):
        print(f"  not ready: {r}")
    verdict = st.get("verdict") or {}
    for p in verdict.get("problems", []):
        print(f"  validator {p['rule']} slide {p.get('slide')} bullet {p.get('bullet')}: {p['message']}")
    deg = st.get("degraded")
    if deg:                       # c4: the Writer failed its rewrites; code put its own texts in their place
        print(f"  DEGRADED: the Writer's text failed {deg['problems_before']} check(s) after its rewrites; code "
              f"replaced bullets {deg['replaced_bullets']}, dropped {deg['dropped_bullets']}, slides by code "
              f"{deg['code_slides']}, slide titles by code {deg['code_slide_titles']} — read it before approving")
    draft = st.get("draft")
    if draft:                     # the slots filled: what the deck says (Phase 6); edits are written in this form
        print(f"  review version (--draft-sha): {approver_request.draft_sha(st)}")
        draft = wp.v2.render_draft(draft, st.get("evidence") or {})
        print(f"  {draft['title']}")
        titles = {t["slide"]: t["title"] for t in draft["slide_titles"]}
        for i, b in enumerate(draft["bullets"]):
            print(f"  [{i:2d}] slide {b['slide']:2d} ({titles.get(b['slide'], '')[:30]}): {b['text']}  "
                  f"<{', '.join(b['evidence_ids'])}>")
    ins = st.get("insight")
    if ins:                       # the analysis behind the deck: what a revise changes (indexes for --analysis)
        mark = {True: " [approver]", False: ""}
        for i, c in enumerate(ins.get("summary") or []):
            print(f"  note summary[{i}]{mark[c.get('origin') == 'approver']}: {c['text']}")
        for i, d in enumerate(ins.get("drivers") or []):
            print(f"  note driver[{i}] {d['vessel_category']}{mark[d.get('origin') == 'approver']}: {d['explanation']}")
        for i, c in enumerate(ins.get("context") or []):
            print(f"  note context[{i}]{mark[c.get('origin') == 'approver']}: {c['text']}")
        for i, c in enumerate(ins.get("caveats") or []):
            print(f"  note caveat[{i}]: {c}")
    if st.get("charts"):
        print(f"  chart variants: {json.dumps(st['charts'], ensure_ascii=False)}")
    if st.get("redrafted_slides"):
        print(f"  slides re-drafted by the last revise: {st['redrafted_slides']} (the others, the additions and the "
              "chart variants kept)")
    elif st.get("redrafted"):
        print("  re-drafted after a revise (before the targeted revise: earlier edits and additions not kept)")
    marked = [b["slide"] for b in (st.get("draft") or {}).get("bullets") or [] if b.get("origin") == "code"]
    if marked or (st.get("draft") or {}).get("removed"):
        print(f"  written by code on slides {sorted(set(marked))}; texts taken out: "
              f"{[(r['slide'], r['why']) for r in st['draft'].get('removed') or []]}")
    rev = st.get("revision") or {}
    if rev.get("failed"):
        print(f"  the last revise could not be shown and was undone: {rev['failed']}")
    if rev.get("edits_skipped"):
        print(f"  analysis edits not applied to the steered notes: {rev['edits_skipped']}")
    if st.get("preview"):
        print(f"  preview (open it before deciding): {st['preview']['path']}")
    if snap.interrupts:
        print(f"  waiting for a decision: {snap.interrupts[0].value['decisions']}")
    for e in st.get("approval_log") or []:      # a refusal's reason, else the approver's comment
        print(f"  log {e['at']} {e['outcome']} by {e.get('approver_employee_id')}: "
              f"{e.get('reason') or e.get('comment') or ''}")
    if st.get("normalized"):
        print(f"  slot-form fixes made by code (D-P7-14): {len(st['normalized'])}")
    if st.get("published"):
        print(f"  published: {st['published']['folder']}")


def request(g, cfg, ctx, a, run_as) -> None:
    """The manager's request in words (approver-request plan, R2): read it on the waiting draft and print what was
    understood; only with --yes is it applied (the same request on the same draft is read from the reply cache, so the
    confirmed run applies exactly what was shown)."""
    ok, why = wp.approver_check(a.employee)
    if not ok:
        raise SystemExit(f"employee {a.employee} may not decide: {why}")
    waiting, st = approver_request.waiting(g, cfg)
    if not waiting:
        raise SystemExit(f"thread {a.thread} is not waiting for a decision (status {st.get('status')})")
    models = roles.Roles()
    p = approver_request.propose(a.request, st, models)
    print(f"  understood: {p.understood or '—'}")
    if p.ask_back:
        print(f"  ask back: {p.ask_back}")
        return
    for i, s in enumerate(p.steps, 1):
        print(f"  step {i}: {json.dumps(s, ensure_ascii=False)}")
    if p.reread_text:
        print("  after the revise, the wording part is read again on the new draft (D-AR-1)")
    if not a.yes:
        print("  nothing applied: re-run with --yes to apply it")
        return
    monitoring.tag(thread_id=a.thread, run_as=run_as)
    with locks.thread_lock(a.thread), tracing.trace(a.thread, entry="resume:request", run_as=run_as) as traced:
        out = approver_request.apply(g, cfg, ctx, p, a.request, a.employee, models, comment=a.comment,
                                     on_update=lambda nodes: print("  done:", ", ".join(nodes) or "interrupt"))
    print(f"  result: {json.dumps(out, ensure_ascii=False)}")
    print(f"  LangSmith: {tracing.describe(traced)}")
    show(g, cfg)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--week", type=int, required=True, choices=range(1, 53), metavar="1..52")
    r.add_argument("--as", dest="employee", type=int, required=True)
    s = sub.add_parser("show")
    s.add_argument("--thread", required=True)
    d = sub.add_parser("resume")
    d.add_argument("--thread", required=True)
    d.add_argument("--as", dest="employee", type=int, required=True)
    d.add_argument("--decision", choices=["approve", "edit", "revise", "reject"])
    d.add_argument("--draft-sha", help="direct decision: the review version printed by show")
    d.add_argument("--request", help="the manager's request in words (approver-request plan): prints what it "
                                     "understood; add --yes to apply it")
    d.add_argument("--yes", action="store_true", help="--request: apply what was understood (R2: confirm first)")
    d.add_argument("--edits", type=Path, help="edit: a JSON file [{bullet, text}]")
    d.add_argument("--add", action="append", default=[], metavar="SLIDE: TEXT",
                   help="edit: a new bullet on a free-text slide 3–9 (repeatable), e.g. --add \"4: Finance will …\"")
    d.add_argument("--chart", action="append", default=[], metavar="JSON",
                   help="edit / revise: a chart variant (repeatable), "
                        "e.g. --chart '{\"chart\": \"trend\", \"weeks\": 8}'")
    d.add_argument("--analysis", type=Path, help="revise: a JSON file of analysis edits [{target, op, index, text, "
                                                 "evidence_ids}]")
    d.add_argument("--steer", help="revise: what the Insight agent should look at again (≤ 300 characters)")
    d.add_argument("--comment")
    lst = sub.add_parser("list")
    lst.add_argument("--week", type=int)
    sch = sub.add_parser("scheduled")
    sch.add_argument("--as", dest="employee", type=int)
    sync = sub.add_parser("reconcile", help="retry database sync of the current immutable approved pack; no model call")
    sync.add_argument("--week", type=int, required=True, choices=range(1, 53), metavar="1..52")
    sync.add_argument("--as", dest="employee", type=int, required=True)
    pr = sub.add_parser("prune")
    pr.add_argument("--dry-run", action="store_true")
    sub.add_parser("report")
    a = ap.parse_args()
    monitoring.init(entry=f"weekly_pack:{a.cmd}", launched_by="task_scheduler" if a.cmd == "scheduled" else "cli")

    if a.cmd == "list":
        print("\n".join(threads(a.week)) or "no thread")
        return
    if a.cmd == "scheduled":
        with monitoring.cron(monitoring.CRON_WEEKLY_PACK) as result:
            result["exit"] = scheduled(a.employee)
        raise SystemExit(result["exit"])
    if a.cmd == "reconcile":
        if not wp.approver_check(a.employee)[0]:
            raise SystemExit("reconciliation requires a Finance manager or CEO")
        manifest = publications.reconcile(REPORTS / f"{wp.REPORT_YEAR}-W{a.week:02d}", wp.store_publication)
        print(json.dumps({"week": a.week, "thread_id": manifest["thread_id"], "db_sync": manifest["db_sync"]}, indent=1))
        raise SystemExit(0 if manifest["db_sync"]["status"] == "synced" else 5)
    g = graph()
    if a.cmd in ("prune", "report"):
        infos = scheduling.describe_all(g, checkpointer.pool(), PREFIX)
        if a.cmd == "prune":
            out = scheduling.prune(g, checkpointer.saver(), infos, LOG / "threads_archive.jsonl", dry_run=a.dry_run)
            rg = route_graph()                    # Agents plan §6b P10-3: the route-advice threads, same rule
            out["route_advice"] = scheduling.prune(rg, checkpointer.saver(),
                                                   scheduling.describe_route_advice(rg, checkpointer.pool()),
                                                   LOG / "threads_archive.jsonl", dry_run=a.dry_run)
            ag = ask_graph()                      # §6d S4: the supervisor's question threads, same rule
            out["ask"] = scheduling.prune(ag, checkpointer.saver(), scheduling.describe_ask(ag, checkpointer.pool()),
                                          LOG / "threads_archive.jsonl", dry_run=a.dry_run)
            arg = arrival_graph()                 # JIT arrival plan: the arrival-advice threads, same rule
            out["arrival_advice"] = scheduling.prune(arg, checkpointer.saver(),
                                                     scheduling.describe_arrival_advice(arg, checkpointer.pool()),
                                                     LOG / "threads_archive.jsonl", dry_run=a.dry_run)
        else:
            out = scheduling.approval_report(scheduling.report_entries(g, infos, REPORTS))
        print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
        return
    if a.cmd == "show":
        show(g, {"configurable": {"thread_id": a.thread}})
        return
    if a.cmd == "run":
        user = context.load_user(a.employee)
        cfg = {"configurable": {"thread_id": next_attempt(a.week)}, "metadata": {"run_as": a.employee}}
        print(f"running week {a.week} as employee {a.employee} ({user.role} / {user.department})")
        monitoring.tag(thread_id=cfg["configurable"]["thread_id"], run_as=a.employee)
        with locks.thread_lock(cfg["configurable"]["thread_id"]), tracing.trace(
                cfg["configurable"]["thread_id"], entry="run", run_as=a.employee) as traced:
            if g.get_state(cfg).values:
                raise SystemExit("this attempt was started by another process; run again for a new attempt")
            for upd in g.stream({"report_week": a.week}, cfg, context=context.RunContext(user),
                                stream_mode="updates", durability="sync"):
                print("  done:", ", ".join(k for k in upd if not k.startswith("__")) or "interrupt")
    else:
        cfg = {"configurable": {"thread_id": a.thread}}
        # the run keeps its identity (P5-5): the tools after an edit and the publisher's record act as the employee
        # who started the pack (checkpoint metadata), not as the approver, who only decides (checked in the graph)
        run_as = next((s.metadata.get("run_as") for s in g.get_state_history(cfg) if s.metadata.get("run_as")), None)
        if run_as is None:
            raise SystemExit(f"thread {a.thread}: no run identity in its checkpoints (not started by this CLI)")
        ctx = context.RunContext(context.load_user(run_as))
        if a.request:
            request(g, cfg, ctx, a, run_as)
            return
        if not a.decision:
            raise SystemExit("resume: give --decision or --request")
        if not a.draft_sha:
            raise SystemExit("resume --decision requires --draft-sha from the pack you reviewed with show")
        decision = {"decision": a.decision, "approver_employee_id": a.employee, "comment": a.comment}
        if a.edits:
            decision["edits"] = json.loads(a.edits.read_text(encoding="utf-8"))
        if a.add:                 # "4: text" → {slide, text}
            decision["additions"] = [{"slide": int(x.split(":", 1)[0]), "text": x.split(":", 1)[1].strip()}
                                     for x in a.add]
        if a.chart:
            decision["charts"] = [json.loads(x) for x in a.chart]
        if a.analysis:
            decision["analysis_edits"] = json.loads(a.analysis.read_text(encoding="utf-8"))
        if a.steer:
            decision["steer"] = a.steer
        monitoring.tag(thread_id=a.thread, run_as=run_as)
        with locks.thread_lock(a.thread), tracing.trace(a.thread, entry="resume", run_as=run_as) as traced:
            snap = g.get_state(cfg)
            if not snap.interrupts or approver_request.draft_sha(snap.values) != a.draft_sha:
                raise SystemExit("this pack changed; show and review it again before deciding")
            for upd in g.stream(Command(resume=decision), cfg, context=ctx, stream_mode="updates",
                                durability="sync"):
                print("  done:", ", ".join(k for k in upd if not k.startswith("__")) or "interrupt")
    print(f"  LangSmith: {tracing.describe(traced)}")
    show(g, cfg)


if __name__ == "__main__":
    main()
