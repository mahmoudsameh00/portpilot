"""Route advice and the voyage watch (plan §3.5; ADR-057 / ADR-058).

- `POST /route-advice` runs the `route_advice` graph exactly as `Route_advice.py ask` does (its own thread
  `route_advice:<employee>:<as_of>:<from>-<to>:<n>`, one trace, the tools' RBAC) in the run executor; the stored
  advice is read by its asker and the CEO.
- The watch is never started here (owner A5: Task Scheduler runs it every 12 h); its saved alerts and runs are level
  1 / Operations data (P11-8), readable by every employee — `watch.read_alerts` still checks the identity.
"""
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request

from pipelines.agents import checkpointer, scheduling, tracing
from pipelines.agents.graphs import route_advice as ra
from pipelines.agents.graphs import voyage_watch as vw
from pipelines.agents.graphs.models import RouteRequest
from pipelines.agents.tools import context, watch
from pipelines.api import audit, runs
from pipelines.api.auth import Signed
from pipelines.api.errors import ApiError, request_id
from pipelines.api.routers.ask import RunEvents
from pipelines.api.schemas import (RouteAdviceDetail, RunAccepted, ThreadRow, WatchAlerts, WatchRunDetail,
                                   WatchRunRow)

router = APIRouter(tags=["operations"])
ROUTE_NODES = frozenset({"inputs", "routes", "costs", "context", "advisor", "validator", "render"})


class RouteIn(RouteRequest):
    """`RouteRequest` + the clock (UTC; default and maximum: the data's as-of); unknown fields refused (plan §9)."""
    model_config = {**RouteRequest.model_config, "extra": "forbid"}
    as_of: datetime | None = None


@router.post("/route-advice", response_model=RunAccepted, status_code=202)
def route_advice(body: RouteIn, p: Signed, request: Request) -> RunAccepted:
    as_of = body.as_of or context.DATA_AS_OF
    try:
        ctx = context.RunContext(p.user, as_of=as_of if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc))
    except ValueError as exc:                                            # a clock past the data
        raise ApiError(422, str(exc), slug="invalid_request") from None
    req = RouteRequest.model_validate(body.model_dump(exclude={"as_of"}))
    user, rid = p.user, request_id(request)
    runner: runs.Runner = request.app.state.runner
    make_roles = request.app.state.roles_factory
    tid = runner.reserve_thread(lambda: ra.new_thread_id(checkpointer.pool(), user.employee_id, ctx.as_of,
                                                         req.origin, req.destination))

    def work(run: runs.Run) -> dict:
        g = ra.build_graph(make_roles(), checkpointer.saver())
        cfg: Any = {"configurable": {"thread_id": tid}, "metadata": {"run_as": user.employee_id, "trigger": "api"},
                    "callbacks": [RunEvents(run, set(), ROUTE_NODES)]}
        with runs.thread_lock(tid), tracing.trace(tid, entry="api:route_advice", run_as=user.employee_id,
                                                  launched_by="api", extra_tags=("graph:route_advice",)):
            run.check_active()
            if g.get_state(cfg).values:
                raise ApiError(409, "this route thread already exists; retry", slug="thread_exists")
            g.invoke({"request": req.model_dump(mode="json")}, cfg, context=ctx, durability="sync")
        out = ra.result_summary(g.get_state(cfg).values)
        audit.record(employee_id=user.employee_id, resource_type="route_advice", resource_id=tid, trace_id=tid,
                     action="ask", decision="allowed", request_id=rid, detail={"status": out["status"]})
        return {"thread": tid, "status": out["status"], "answer": out, "not_permitted": [], "evidence": {},
                "problems": out["problems"] or [], "stop_reason": None, "model_calls": out["model_calls"],
                "cached": out["cached"]}

    run = runner.submit(user.employee_id, "route_advice", work, thread_id=tid)
    base = str(request.url_for("run_events", run_id=run.id).path).removesuffix("/events")
    return RunAccepted(run_id=run.id, thread_id=tid, events_url=f"{base}/events", run_url=base)


def _route_reader(request: Request):
    return ra.build_graph(None, checkpointer.saver())


@router.get("/route-advice", response_model=list[ThreadRow])
def list_route_advice(p: Signed, request: Request) -> list[dict]:
    prefix = ra.THREAD_PREFIX if p.user.role == "ceo" else f"{ra.THREAD_PREFIX}{p.employee_id}:"
    infos = scheduling.describe_route_advice(_route_reader(request), checkpointer.pool(), prefix)
    return [{"thread_id": i.thread_id, "state": i.state, "status": i.status, "last_at": i.last_at} for i in infos]


@router.get("/route-advice/{thread_id}", response_model=RouteAdviceDetail)
def get_route_advice(thread_id: str, p: Signed, request: Request) -> dict:
    if p.user.role != "ceo" and ra.thread_owner(thread_id) != p.employee_id:
        audit.record(employee_id=p.employee_id, resource_type="route_advice", resource_id=thread_id, action="read",
                     decision="denied", request_id=request_id(request))
        raise ApiError(404, "no such route advice", slug="not_found")
    st = _route_reader(request).get_state({"configurable": {"thread_id": thread_id}}).values
    if not st:
        raise ApiError(404, "no such route advice", slug="not_found")
    return {"thread_id": thread_id, **ra.result_summary(st)}


# --- the voyage watch (read only) ---------------------------------------------------------------------------------
@router.get("/voyage-watch/alerts", response_model=WatchAlerts)
def watch_alerts(p: Signed, thread: str | None = None, vessel: int | None = None, high: bool = False) -> dict:
    """The tool's own answer: `ok` with the alerts, `no_data` (no saved run) or `not_permitted` — an answer, 200."""
    return watch.read_alerts(p.user, thread, vessel, high)


def _watch_reader(p, request: Request, resource_id: str = "runs") -> None:
    """The runs hold the same level-1 Operations data as the alerts: the same identity check (ADR-006, P11-8)."""
    if not watch.can_read(p.user):
        audit.record(employee_id=p.employee_id, resource_type="voyage_watch", resource_id=resource_id, action="read",
                     decision="denied", request_id=request_id(request))
        raise ApiError(403, "the voyage watch is level-1 Operations data (ADR-006)", slug="not_allowed")


@router.get("/voyage-watch/runs", response_model=list[WatchRunRow])
def watch_runs(p: Signed, request: Request) -> list[dict]:
    _watch_reader(p, request)
    g = vw.build_graph(None, checkpointer.saver(), vw.REPORTS_DIR)
    return [{"thread_id": i.thread_id, "state": i.state, "status": i.status, "last_at": i.last_at,
             "run_as": i.run_as} for i in scheduling.describe_voyage_watch(g, checkpointer.pool())]


@router.get("/voyage-watch/runs/{thread_id}", response_model=WatchRunDetail)
def watch_run(thread_id: str, p: Signed, request: Request) -> dict:
    _watch_reader(p, request, thread_id)
    if not thread_id.startswith(vw.THREAD_PREFIX):
        raise ApiError(404, "no such watch run", slug="not_found")
    g = vw.build_graph(None, checkpointer.saver(), vw.REPORTS_DIR)
    st = g.get_state({"configurable": {"thread_id": thread_id}}).values
    if not st:
        raise ApiError(404, "no such watch run", slug="not_found")
    etas = (st.get("result") or {}).get("etas") or []       # the run's ETA table (rule R), D-FE-10
    return {"thread_id": thread_id, **vw.result_summary(st), "etas": etas}
