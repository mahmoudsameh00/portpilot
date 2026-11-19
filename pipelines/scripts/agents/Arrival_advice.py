"""Ask the arrival advisor (Just-in-Time arrival, JIT arrival plan §3d; the graph: `graphs/arrival_advice.py`).

Commands (from the project root):
    uv run python pipelines/scripts/agents/Arrival_advice.py ask --vessel 28 --as 13
        one question as employee 13 (role and department from PostgreSQL; the tools apply RBAC, ADR-006) with the RTA
        known at the clock from the port's messages (`port_call_messages`, migration 030): prints the status, the
        recommendation, the summary and the option table, the reasons and risks with their numbers filled from the
        tools, the assumptions and the sources; one thread `arrival_advice:<employee>:<as_of>:<vessel>:<n>` in
        agent_state; traced in LangSmith (project nilegate-agents) when LANGSMITH_API_KEY is set.
    uv run python pipelines/scripts/agents/Arrival_advice.py ask --vessel 28 --rta 2026-09-15T14:00Z --as 13 \
        [--port NLRTM] [--location pilot_boarding_place] [--as-of 2026-09-13T00:00Z]
        the same with the RTA given here (it wins over a stored message, and is said so).
    uv run python pipelines/scripts/agents/Arrival_advice.py rta --vessel 28 --as 13 [--as-of …]
        the RTA known at the clock for the vessel's current port call (no model, no thread).
    uv run python pipelines/scripts/agents/Arrival_advice.py show <thread>     the stored answer of a thread
    uv run python pipelines/scripts/agents/Arrival_advice.py list --as 13      that employee's questions

Reads:   PostgreSQL read-only through the tools, MongoDB AIS (read-only user), searoute locally, Open-Meteo and
         PortWatch (cached), the `writer` role's models (ADR-045; llm.py cache and quota).
Writes:  checkpoints in agent_state (login ports_agent); deleted after 30 days by the retention
         (`Weekly_pack.py prune`, and every scheduled firing). LangSmith traces when a key exists.
Re-run:  `ask` always starts a new thread; `rta` / `show` / `list` read only.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.runnables import RunnableConfig

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from pipelines.agents import checkpointer, locks, monitoring, roles as roles_mod, scheduling, tracing  # noqa: E402
from pipelines.agents.graphs import arrival_advice as aa  # noqa: E402
from pipelines.agents.graphs.models import ArrivalRequest  # noqa: E402
from pipelines.agents.tools import arrival, context  # noqa: E402


def ask(req: ArrivalRequest, employee: int, as_of: datetime, roles=None) -> tuple[str, dict, bool]:
    """(thread id, final state, traced). `roles` = `Roles()` (real models) unless a check passes `FakeRoles`."""
    user = context.load_user(employee)
    ctx = context.RunContext(user, as_of=as_of)                  # refuses a clock past the data
    g = aa.build_graph(roles or roles_mod.Roles(), checkpointer.saver())
    tid = aa.new_thread_id(checkpointer.pool(), employee, as_of, req.vessel_id)
    cfg: RunnableConfig = {"configurable": {"thread_id": tid}, "metadata": {"run_as": employee, "trigger": "cli"}}
    monitoring.tag(thread_id=tid, run_as=employee)
    with locks.thread_lock(tid), tracing.trace(tid, entry="arrival_advice", run_as=employee,
                                              extra_tags=("graph:arrival_advice",)) as traced:
        if g.get_state(cfg).values:
            raise RuntimeError("this arrival thread was started by another process; retry for a new thread")
        g.invoke({"request": req.model_dump(mode="json")}, cfg, context=ctx, durability="sync")
    return tid, g.get_state(cfg).values, traced


summary = aa.result_summary


def _instant(s: str | None) -> datetime:
    if not s:
        return context.DATA_AS_OF
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask")
    a.add_argument("--vessel", type=int, required=True)
    a.add_argument("--rta", help="the requested time of arrival, ISO with its zone, e.g. 2026-09-15T14:00Z")
    a.add_argument("--port", help="UN/LOCODE; must be the vessel's destination")
    a.add_argument("--location", choices=list(arrival.LOCATIONS), default="berth")
    a.add_argument("--as", dest="employee", type=int, required=True)
    a.add_argument("--as-of", help="the clock, ISO (default: the data's as-of instant)")
    r = sub.add_parser("rta")
    r.add_argument("--vessel", type=int, required=True)
    r.add_argument("--as", dest="employee", type=int, required=True)
    r.add_argument("--as-of")
    s = sub.add_parser("show")
    s.add_argument("thread")
    li = sub.add_parser("list")
    li.add_argument("--as", dest="employee", type=int, required=True)
    args = ap.parse_args()
    monitoring.init(entry=f"arrival_advice:{args.cmd}")

    if args.cmd == "ask":
        req = ArrivalRequest(vessel_id=args.vessel, port=args.port.upper() if args.port else None,
                             rta_utc=_instant(args.rta) if args.rta else None, location=args.location)
        tid, st, traced = ask(req, args.employee, _instant(args.as_of))
        print(json.dumps({"thread": tid, **summary(st)}, ensure_ascii=False, indent=1, default=str))
        print(f"LangSmith: {tracing.describe(traced)}")
        return
    if args.cmd == "rta":
        user, as_of = context.load_user(args.employee), _instant(args.as_of)
        context.RunContext(user, as_of=as_of)                     # the same clock rule as a question
        call = arrival.vessel_call(args.vessel)
        if call is None:
            raise SystemExit(f"no voyage for vessel {args.vessel}")
        print(json.dumps(arrival.rta_known(user, args.vessel, call[0], call[1], as_of).model_dump(mode="json"),
                         ensure_ascii=False, indent=1))
        return
    g = aa.build_graph(None, checkpointer.saver())               # reading only: no model is called
    if args.cmd == "show":
        st = g.get_state({"configurable": {"thread_id": args.thread}}).values
        print(json.dumps(summary(st) if st else {"error": f"no thread {args.thread}"}, ensure_ascii=False, indent=1,
                         default=str))
        return
    infos = scheduling.describe_arrival_advice(g, checkpointer.pool(), f"{aa.THREAD_PREFIX}{args.employee}:")
    for i in infos:
        print(f"{i.thread_id}  {i.state:<8} {i.status or '-'}  {i.last_at:%Y-%m-%d %H:%M}")
    print(f"{len(infos)} question(s)")


if __name__ == "__main__":
    main()
