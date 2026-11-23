"""The product graphs as tools of the supervisor (Agents plan Phase 12, §6d P12-2, S2).

`route_advice` runs the ADR-057 graph (`graphs/route_advice.py`) as one tool call: its own PostgresSaver thread
`route_advice:<employee>:<as_of>:<from>-<to>:<n>` (resumable, kept 30 days by the same retention as the CLI's), the
run context's user and clock, its own Validator and number slots — the supervisor only cites its rows, it never
recomputes a route number. Built per agent by `make_route_advice_tool(roles)`, so a check injects fake roles. Inside
a traced supervisor question the graph's runs appear under that question's trace (no trace of its own here).

Rows (the contract the S2 Q&A golden items fix): the graph's code results, one row per `route` — `suez` / `cape` /
`direct` (route.compare), `difference` (Cape − Suez, with `cheaper_route`), `traffic` (Suez transits vs a year
earlier, when PortWatch answered) — plus one row `route = "advice"`: the graph status, the recommendation, the
rendered headline / reasons / risks / assumptions and the `thread_id`.

Statuses (S2 decision 3): ok / no_suez_on_route / suez_only → `ok` with the rows; an advice its Validator stops
(`validation_failed`) or an unreadable model reply (`output_invalid`) → still `ok` with the code rows and the advice row
marked with that status and no recommendation (the numbers are the code's; only the words failed); not_permitted /
no_data → the same status, no rows. Access is checked by the graph's tools before any model call (level 1).
"""
import re
from datetime import datetime, timezone

from langchain.tools import ToolRuntime, tool
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from pipelines.agents import checkpointer as cp
from pipelines.agents import locks
from pipelines.agents.graphs import route_advice as ra
from pipelines.agents.graphs.models import RouteRequest
from pipelines.agents.tools import context
from pipelines.agents.tools.schemas import Source, ToolResult

CODE_ROWS = ("route.compare", "route.difference", "route.traffic")
WORDS_FAILED = ("validation_failed", "output_invalid")
MAX_THREAD_TRIES = 50                 # route thread numbers tried before giving up (one per earlier same-day question)


class RouteAdviceArgs(RouteRequest):
    vessel_id: int | None = Field(default=None, ge=1, description="one of PortPilot's vessels (or give vessel_type + "
                                                                  "condition + scnt_tons for a hypothetical vessel)")
    vessel_type: str | None = Field(default=None, description="tariff vessel category of a hypothetical vessel")
    condition: str | None = Field(default=None, description="Laden or Ballast (a hypothetical vessel)")
    scnt_tons: float | None = Field(default=None, gt=0, description="Suez Canal Net Tonnage of a hypothetical vessel")
    origin: str = Field(pattern=r"^[A-Z]{2}[A-Z2-9]{3}$", description="UN/LOCODE of the departure port, e.g. SGSIN")
    destination: str = Field(pattern=r"^[A-Z]{2}[A-Z2-9]{3}$", description="UN/LOCODE of the arrival port, e.g. NLRTM")
    speed_kn: float | None = Field(default=None, ge=4, le=25, description="speed in knots (default: the vessel's "
                                                                          "service speed)")


def _rows(res: dict | None) -> list[dict]:
    res = res or {}
    return list(res.get("rows") or []) if res.get("status") == "ok" else []


def run_route_advice(user, roles, as_of: datetime | None = None, saver=None, pool=None, **args) -> ToolResult:
    """One route question through the graph in a new thread; the ToolResult of the module docstring."""
    req = RouteRequest.model_validate(RouteAdviceArgs.model_validate(args).model_dump())
    ctx = context.RunContext(user, as_of=as_of or context.DATA_AS_OF)          # refuses a clock past the data
    pool = pool or cp.pool()
    g = ra.build_graph(roles, saver or cp.saver())
    tid = ra.new_thread_id(pool, user.employee_id, ctx.as_of, req.origin, req.destination)
    # The number comes from PostgreSQL's checkpoints; the thread itself lives in `saver`. A thread that already
    # holds a state — another process took the number first, or the saver is not the PostgreSQL one (the
    # evaluations run on InMemorySaver, where the same route asked twice got the same number and the whole
    # question failed, 2026-11-13) — is never written into: the next free number is taken, under its own lock.
    for _ in range(MAX_THREAD_TRIES):
        cfg: RunnableConfig = {"configurable": {"thread_id": tid},
                               "metadata": {"run_as": user.employee_id, "trigger": "supervisor"}}
        with locks.thread_lock(tid):
            if not g.get_state(cfg).values:
                g.invoke({"request": req.model_dump(mode="json")}, cfg, context=ctx, durability="sync")
                break
        tid = re.sub(r"(\d+)$", lambda m: str(int(m.group(1)) + 1), tid)
    else:
        raise RuntimeError(f"no free route thread after {MAX_THREAD_TRIES} numbers; retry")
    st = g.get_state(cfg).values
    res, status, ev = st.get("result") or {}, st.get("status") or "ok", st.get("evidence") or {}
    if status in ("not_permitted", "no_data"):
        return ToolResult(tool="route_advice", status=status,
                          note="; ".join(res.get("problems") or []) or f"route advice: {status} (thread {tid})")
    rows = [r for key in CODE_ROWS for r in _rows(ev.get(key))]
    if not rows:                                    # nothing computed (a route or vessel the tools could not read)
        return ToolResult(tool="route_advice", status="context_unavailable",
                          note=f"route advice ended {status} with no computed rows (thread {tid})")
    failed = status in WORDS_FAILED
    rows.append({"route": "advice", "status": status, "recommendation": None if failed else res.get("recommendation"),
                 "headline": None if failed else res.get("headline"),
                 "reasons": [] if failed else res.get("reasons") or [], "risks": [] if failed else res.get("risks") or [],
                 "assumptions": res.get("assumptions") or [], "problems": res.get("problems") or [],
                 "thread_id": tid})
    flt = (f"{req.origin} → {req.destination}, "
           + (f"vessel_id = {req.vessel_id}" if req.vessel_id is not None
              else f"{req.vessel_type} / {req.condition} / {req.scnt_tons} SCNT")
           + (f" at {req.speed_kn} kn" if req.speed_kn is not None else "") + f", as of {ctx.as_of.isoformat()}")
    note = ("numbers computed by code (sea_route, vessel_params, compute_toll; days = distance / (speed × 24)); "
            + ("the advice failed its Validator — cite the rows, give no recommendation" if failed
               else "the advice passed the route Validator (the cheaper route unless a cited risk)"))
    return ToolResult(tool="route_advice", status="ok", rows=rows, note=note,
                      source=Source(kind="library", name=f"route_advice graph (thread {tid})", filter=flt))


def make_route_advice_tool(roles, saver=None, pool=None):
    """The `route_advice` LangChain tool bound to `roles` (real `Roles()` or a check's `FakeRoles`)."""

    @tool("route_advice", args_schema=RouteAdviceArgs)
    def route_advice_tool(runtime: ToolRuntime, **args) -> dict:
        """Suez Canal or the Cape of Good Hope for one voyage: distance, sea days, fuel and its cost in SDR, the Suez
        dues, the Cape − Suez difference and the cheaper route, with a validated recommendation (one of PortPilot's
        vessels, or a hypothetical one). Rows by `route`: the Suez dues = the `suez` row's suez_dues_sdr; the saving
        or extra of the Cape = the `difference` row's change_* fields (change_total_sdr, change_sea_days)."""
        return run_route_advice(context.user_of(runtime), roles, as_of=context.as_of_of(runtime), saver=saver,
                                pool=pool, **args).model_dump(mode="json")

    return route_advice_tool


# --- arrival_advice (JIT arrival plan §3d): the arrival graph as one tool call, the same pattern ------------------------
# Rows keyed by `option`: the graph's option rows (keep / jit / floor / catch_up / cape), one `summary` row (the RTA,
# the target, the situation, the rule's choice) and one `advice` row (status, recommendation, rendered words, thread).

ARRIVAL_STOPS = ("not_permitted", "no_data", "not_at_sea", "not_destination", "no_rta")


class ArrivalAdviceArgs(BaseModel):
    vessel_id: int = Field(ge=1, description="one of PortPilot's vessels, at sea")
    port: str | None = Field(default=None, pattern=r"^[A-Z]{2}[A-Z2-9]{3}$",
                             description="UN/LOCODE of the port the question names (must be the vessel's destination)")
    rta_utc: str | None = Field(default=None, description="the requested time of arrival the question gives, ISO "
                                                          "with Z, e.g. 2026-09-15T14:00Z; leave empty to use the "
                                                          "RTA the port sent (known at the clock)")
    location: str = Field(default="berth", pattern="^(berth|pilot_boarding_place)$",
                          description="where the RTA applies: berth (default) or pilot_boarding_place")


def run_arrival_advice(user, roles, as_of: datetime | None = None, saver=None, pool=None, **args) -> ToolResult:
    """One arrival question through the graph in a new thread (rows keyed by option, see above)."""
    from pipelines.agents.graphs import arrival_advice as aa
    from pipelines.agents.graphs.models import ArrivalRequest

    a = ArrivalAdviceArgs.model_validate(args)
    rta = datetime.fromisoformat(a.rta_utc.replace("Z", "+00:00")) if a.rta_utc else None
    if rta is not None and rta.tzinfo is None:
        rta = rta.replace(tzinfo=timezone.utc)
    req = ArrivalRequest(vessel_id=a.vessel_id, port=a.port, rta_utc=rta, location=a.location)  # pyright: ignore[reportArgumentType]
    ctx = context.RunContext(user, as_of=as_of or context.DATA_AS_OF)
    pool = pool or cp.pool()
    g = aa.build_graph(roles, saver or cp.saver())
    tid = aa.new_thread_id(pool, user.employee_id, ctx.as_of, req.vessel_id)
    for _ in range(MAX_THREAD_TRIES):
        cfg: RunnableConfig = {"configurable": {"thread_id": tid},
                               "metadata": {"run_as": user.employee_id, "trigger": "supervisor"}}
        with locks.thread_lock(tid):
            if not g.get_state(cfg).values:
                g.invoke({"request": req.model_dump(mode="json")}, cfg, context=ctx, durability="sync")
                break
        tid = re.sub(r"(\d+)$", lambda m: str(int(m.group(1)) + 1), tid)
    else:
        raise RuntimeError(f"no free arrival thread after {MAX_THREAD_TRIES} numbers; retry")
    st = g.get_state(cfg).values
    res, status = st.get("result") or {}, st.get("status") or "ok"
    if status in ARRIVAL_STOPS:
        return ToolResult(tool="arrival_advice", status="not_permitted" if status == "not_permitted" else "no_data",
                          note="; ".join(res.get("problems") or []) or f"arrival advice: {status} (thread {tid})")
    failed = status in WORDS_FAILED
    rows = [dict(o) for o in res.get("options") or []]
    rows.append({"option": "summary", **{k: v for k, v in (res.get("summary") or {}).items() if k != "vessel_id"},
                 "vessel_id": req.vessel_id})
    rows.append({"option": "advice", "status": status, "recommendation": None if failed else res.get("recommendation"),
                 "headline": None if failed else res.get("headline"), "reasons": [] if failed else res.get("reasons") or [],
                 "risks": [] if failed else res.get("risks") or [], "assumptions": res.get("assumptions") or [],
                 "thread_id": tid})
    note = ("numbers computed by code (voyage_status, vessel_params, the RTA message; cube-law fuel); rows keyed by "
            "option: keep / jit / floor / catch_up / cape, `summary` (rta_utc, target_utc, situation, keep_wait_h, "
            "rule_option) and `advice` — cite e.g. {<id>[jit]:speed_kn}, {<id>[summary]:keep_wait_h}; rta_utc is "
            "the port's requested time; arrival_utc is the option's ETA. The planning target is RTA minus margin_h; "
            "rounding the sailing speed can shift the ETA. "
            + ("the advice failed its Validator — cite the rows, give no recommendation" if failed
               else "the advice passed the arrival Validator (the cheapest option at the RTA location by the RTA unless a "
                    "cited risk)"))
    return ToolResult(tool="arrival_advice", status="ok", rows=rows, note=note,
                      source=Source(kind="library", name=f"arrival_advice graph (thread {tid})",
                                    filter=f"vessel_id = {req.vessel_id}, RTA "
                                           f"{'given ' + a.rta_utc if a.rta_utc else 'known at the clock'}, "
                                           f"as of {ctx.as_of.isoformat()}"))


def make_arrival_advice_tool(roles, saver=None, pool=None):
    """The `arrival_advice` LangChain tool bound to `roles` (real `Roles()` or a check's `FakeRoles`)."""

    @tool("arrival_advice", args_schema=ArrivalAdviceArgs)
    def arrival_advice_tool(runtime: ToolRuntime, **args) -> dict:
        """Just-in-Time arrival for one of PortPilot's vessels at sea: given the port's requested time of arrival
        (the RTA the port sent, or one in the question), what speed to sail — keep the speed and wait at anchor, slow
        down to arrive just in time, the lowest allowed speed, speed up, or the Cape — with arrival times, waiting
        hours, fuel in tonnes and SDR per option and a validated recommendation. Rows keyed by option (keep, jit,
        floor, catch_up, cape, summary, advice)."""
        return run_arrival_advice(context.user_of(runtime), roles, as_of=context.as_of_of(runtime), saver=saver,
                                  pool=pool, **args).model_dump(mode="json")

    return arrival_advice_tool
