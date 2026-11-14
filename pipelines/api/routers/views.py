"""The chart catalogue and the "smart" finance view (approver-additions plan §2d, owner C3 / D5; ADR-066).

- `GET /charts/catalogue` — the variants the weekly pack's approver and a reader may ask for (no data).
- `POST /views` with `choice` — code only: the view drawn as the asker (200, a `ViewSpec`).
- `POST /views` with `question` — one structured model call picks the choice from the catalogue (it never sees
  data), then code draws it: a run (202 + SSE like a question), its `answer` event carrying `view` (or, when the
  question names no week, an ask-back in `answer` and no view — D5).

Who: the finance views' RBAC (ADR-006: level 2, Finance + every manager + the CEO), checked here to answer 403 early
and again inside `finance_kpi` for every result.
"""
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import Field, model_validator

from pipelines.agents import tracing, views
from pipelines.agents.deck import charts
from pipelines.agents.graphs import models as m
from pipelines.agents.roles import StructuredError
from pipelines.agents.tools import context
from pipelines.api import audit, runs
from pipelines.api.auth import Principal, Signed
from pipelines.api.errors import ApiError, request_id
from pipelines.api.schemas import ChartCatalogue, RunAccepted, Strict

router = APIRouter(tags=["views"])


class ViewIn(Strict):
    choice: m.ViewChoice | None = None
    question: str | None = Field(default=None, min_length=3, max_length=300)

    @model_validator(mode="after")
    def _one(self):
        if (self.choice is None) == (self.question is None):
            raise ValueError("give exactly one of `choice` (code only) or `question` (in words)")
        return self


def _reader(p: Principal) -> None:
    if not context.permitted(p.user, context.FINANCE_VIEWS):
        raise ApiError(403, "the finance views are Finance data (level 2)", slug="not_allowed")


def _record(p: Principal, request: Request, choice: m.ViewChoice | None, decision: str) -> None:
    audit.record(employee_id=p.employee_id, resource_type="view", resource_id=choice.kind if choice else "question",
                 action="view", decision=decision, request_id=request_id(request),
                 detail={"choice": choice.model_dump(exclude_none=True)} if choice else None)


@router.get("/charts/catalogue", response_model=ChartCatalogue)
def catalogue(p: Signed) -> dict:
    """The chart variants (no data): the pack's charts with their options and the reader's views."""
    return charts.catalogue()


@router.post("/views", response_model=None, status_code=200,
             responses={200: {"model": m.ViewSpec, "description": "a choice: the view drawn"},
                        202: {"model": RunAccepted, "description": "a question: a run whose answer carries the view"}})
def view(body: ViewIn, p: Signed, request: Request) -> Any:
    _reader(p)
    if body.choice is not None:
        if body.choice.week is None:
            raise ApiError(422, views.ASK_WEEK, slug="week_needed")
        try:
            spec = views.fetch(p.user, body.choice)
        except views.ViewUnavailable as exc:
            _record(p, request, body.choice, "denied" if exc.status == "not_permitted" else "allowed")
            raise ApiError(403 if exc.status == "not_permitted" else 404, str(exc), slug=exc.status) from exc
        _record(p, request, body.choice, "allowed")
        return spec.model_dump(mode="json")
    question, user, rid, roles_factory = body.question or "", p.user, request_id(request), request.app.state.roles_factory

    def work(run: runs.Run) -> dict:
        out: dict = {"thread": None, "status": "answered", "answer": None, "view": None, "not_permitted": [],
                     "evidence": {}, "problems": [], "stop_reason": None, "model_calls": 0, "cached": 0}
        with tracing.trace(f"view:{run.id}", entry="api:view", run_as=user.employee_id, launched_by="api"):
            try:
                choice, usage = views.choose(question, roles_factory())
            except StructuredError as exc:
                return {**out, "status": "output_invalid", "stop_reason": str(exc)[:300]}
        out.update(model_calls=usage["calls"], cached=usage["cached"])
        if choice.week is None:                    # D5: ask back, never guess the week
            return {**out, "status": "ask_back", "answer": views.ASK_WEEK}
        try:
            spec = views.fetch(user, choice)
        except views.ViewUnavailable as exc:
            return {**out, "status": exc.status, "not_permitted": ["finance_kpi"] if exc.status == "not_permitted"
                    else [], "stop_reason": str(exc)[:300]}
        audit.record(employee_id=user.employee_id, resource_type="view", resource_id=choice.kind, action="view",
                     decision="allowed", request_id=rid, detail={"choice": choice.model_dump(exclude_none=True)})
        return {**out, "answer": spec.caption, "view": spec.model_dump(mode="json")}

    run = request.app.state.runner.submit(p.employee_id, "view", work)
    base = str(request.url_for("run_events", run_id=run.id).path).removesuffix("/events")
    return JSONResponse(RunAccepted(run_id=run.id, thread_id=None, events_url=f"{base}/events",
                                    run_url=base).model_dump(), status_code=202)
