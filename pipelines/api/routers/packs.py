"""The weekly finance pack (plan §3.4; ADR-050 / ADR-051 / ADR-054): its threads, the draft waiting for a decision,
the PPTX preview and deck, and the decision itself — the same `Command(resume=…)` as `Weekly_pack.py resume`.

The API starts no pack (owner A5: Task Scheduler does, one pending at a time). Who: reading = the finance views'
RBAC (ADR-006: Finance, every manager, the CEO; `/me.products.packs_read`); deciding = the graph's own approver rule
(a Finance manager or the CEO), checked here to answer 403 early and again by the graph at the decision. The run keeps
the identity it started with (checkpoint metadata `run_as`, P5-5): the approver only decides.

Files are served only from paths the server computes from the state, inside the reports folder, with the SHA-256
the state recorded for a preview — never a path from the client.
"""
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse
from langgraph.types import Command
from pydantic import Field, model_validator

from pipelines.agents import approver_request as ar
from pipelines.agents import checkpointer, publications, scheduling, tracing, views
from pipelines.agents.graphs import models as gm
from pipelines.agents.graphs import weekly_pack as wp
from pipelines.agents.tools import context
from pipelines.api import audit, runs
from pipelines.api.auth import Principal, Signed
from pipelines.api.errors import ApiError, request_id
from pipelines.api.routers.ask import RunEvents
from pipelines.api.schemas import ApprovalReport, PackAllowed, PackRow, PackView, RunAccepted, Strict

router = APIRouter(prefix="/packs", tags=["packs"])
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
# + the nodes a revise runs (approver-additions plan Phase D): the Insight agent again, the Writer, a restore
PACK_NODES = frozenset({"validator", "approval", "publisher", "fallback", "insight_llm", "insight_tools",
                        "insight_notes", "writer", "revise_failed"})


class Edit(Strict):
    bullet: int = Field(ge=0, le=200)
    text: str = Field(min_length=1, max_length=600)


class DecisionIn(Strict):
    """approve / edit (text edits, additions, chart variants) / revise (analysis edits and / or a steer, chart
    variants; the deck is drafted again) / reject — one kind per decision (approver-additions plan D1)."""
    decision: Literal["approve", "edit", "revise", "reject"]
    edits: list[Edit] = Field(default_factory=list, max_length=40)
    additions: list[gm.Addition] = Field(default_factory=list, max_length=14)
    charts: list[gm.ChartChoice] = Field(default_factory=list, max_length=gm.MAX_CHART_CHANGES)
    analysis_edits: list[gm.AnalysisEdit] = Field(default_factory=list, max_length=gm.MAX_ANALYSIS_EDITS)
    steer: str | None = Field(default=None, min_length=1, max_length=gm.MAX_STEER_CHARS)
    comment: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _kind(self):
        # the graph's own shape rules (D1, caps) answered as a 422 before a run starts
        gm.ApprovalDecision.model_validate({**self.model_dump(exclude={"draft_sha"}), "approver_employee_id": 1})
        return self

    def changes(self) -> dict:
        return {k: v for k, v in self.model_dump(mode="json", exclude_none=True).items()
                if k not in ("decision", "comment", "draft_sha") and v}


class DirectDecisionIn(DecisionIn):
    draft_sha: str = Field(pattern=r"^[0-9a-f]{16}$")


def require_review(g, cfg, expected: str) -> None:
    snap = g.get_state(cfg)
    if not snap.interrupts or ar.draft_sha(snap.values) != expected:
        raise ApiError(409, "the pack changed; reload it and review it before deciding", slug="stale")


def _reader(p: Principal) -> None:
    if not context.permitted(p.user, context.FINANCE_VIEWS):
        raise ApiError(403, "the weekly finance pack is Finance data (level 2)", slug="not_allowed")


def _graph(request: Request, with_models: bool = False):
    roles = request.app.state.roles_factory() if with_models else None
    return wp.build_graph(roles, checkpointer.saver(), request.app.state.reports_dir)


def _ours(request: Request, thread_id: str) -> None:
    if scheduling.parse_thread(thread_id, request.app.state.pack_prefix) is None:
        raise ApiError(404, "no such pack", slug="not_found")


def _inside(request: Request, path: str | None) -> Path:
    root = Path(request.app.state.reports_dir).resolve()
    f = Path(path or "").resolve()
    if not path or not f.is_file() or root not in f.parents:
        raise ApiError(404, "no such file", slug="not_found")
    return f


def charts_drawn(st: dict) -> dict[str, list[dict]]:
    """The series each chart slide of the draft draws (`render.build_spec`, the renderer's own data): the web draws the
    same numbers the PPTX will show (Frontend plan F0). Empty when there is no draft."""
    if not st.get("draft") or not st.get("evidence"):
        return {}
    spec = wp.render.build_spec(st["draft"], st["evidence"], st.get("readiness") or {}, wp.DRAFT_LABEL,
                                st.get("charts"))
    out: dict[str, list[dict]] = {}
    for n, els in enumerate(spec, 1):
        for el in els:
            if el.kind == "chart" and el.chart:
                c = el.chart
                out.setdefault(str(n), []).append({
                    "name": el.name, "type": c.get("type"), "categories": list(c.get("categories") or []),
                    "series": [{"name": name, "values": list(values)} for name, values in c.get("series") or []],
                    "fmt": c.get("fmt"), "highlight": c.get("highlight")})
    return out


def allowed(st: dict, waiting: bool, employee_id: int) -> PackAllowed:
    """What the approver may still do (the graph's own limits, approver plan D1–D3), so the UI hard-codes none."""
    revised = sum(1 for e in st.get("approval_log") or [] if e.get("outcome") == "revised")
    return PackAllowed(decide=waiting and wp.approver_check(employee_id)[0],
                       addition_slides=list(wp.v2.ADDITION_SLIDES), max_additions=wp.v2.MAX_ADDITIONS,
                       max_chart_changes=gm.MAX_CHART_CHANGES, max_analysis_edits=gm.MAX_ANALYSIS_EDITS,
                       max_steer_chars=gm.MAX_STEER_CHARS, revise_left=max(0, wp.MAX_REVISES - revised))


def publication_status(state: dict, thread_id: str) -> str:
    published = state.get("published") or {}
    folder = published.get("week_folder") or published.get("folder")
    return publications.sync_status(Path(folder), thread_id) if folder else "unknown"


def view(g, thread_id: str, employee_id: int | None = None) -> dict:
    """`Weekly_pack.py show` as data (+ `allowed` and `charts_drawn` for the web when an employee asks)."""
    snap = g.get_state({"configurable": {"thread_id": thread_id}})
    st = snap.values
    if not st:
        raise ApiError(404, "no such pack", slug="not_found")
    draft = wp.v2.render_draft(st["draft"], st.get("evidence") or {}) if st.get("draft") else None
    return {"thread_id": thread_id, "draft_sha": ar.draft_sha(st), "status": st.get("status"), "next": list(snap.next),
            "week": st.get("report_week"), "readiness": (st.get("readiness") or {}).get("reasons", []),
            "validator_problems": (st.get("verdict") or {}).get("problems", []), "degraded": st.get("degraded"),
            "draft": draft, "has_preview": bool(st.get("preview")),
            "decisions": snap.interrupts[0].value.get("decisions") if snap.interrupts else [],
            "approval_log": st.get("approval_log") or [], "form_fixes": len(st.get("normalized") or []),
            "published": bool(st.get("published")),
            "publication_sync": publication_status(st, thread_id),
            # approver-additions plan: the analysis behind the deck, the chart variants, whether it was re-drafted
            "insight": st.get("insight"), "charts": st.get("charts") or {}, "redrafted": bool(st.get("redrafted")),
            "revision": st.get("revision"),
            **({"allowed": allowed(st, bool(snap.interrupts), employee_id), "charts_drawn": charts_drawn(st)}
               if employee_id is not None else {})}


@router.get("", response_model=list[PackRow])
def list_packs(p: Signed, request: Request) -> list[dict]:
    _reader(p)
    infos = scheduling.describe_all(_graph(request), checkpointer.pool(), request.app.state.pack_prefix)
    return [{"thread_id": i.thread_id, "week": i.week, "attempt": i.attempt, "state": i.state, "status": i.status,
             "last_at": i.last_at} for i in infos]


@router.get("/report", response_model=ApprovalReport)
def report(p: Signed, request: Request) -> dict:
    """G5: approve / edit / reject counts and the edited slides (ADR-054), for those who may decide."""
    _reader(p)
    if not wp.approver_check(p.employee_id)[0]:
        raise ApiError(403, "a Finance manager or the CEO", slug="not_allowed")
    g = _graph(request)
    infos = scheduling.describe_all(g, checkpointer.pool(), request.app.state.pack_prefix)
    return scheduling.approval_report(scheduling.report_entries(g, infos, Path(request.app.state.reports_dir)))


@router.get("/{thread_id}", response_model=PackView)
def get_pack(thread_id: str, p: Signed, request: Request) -> dict:
    _reader(p)
    _ours(request, thread_id)
    return view(_graph(request), thread_id, p.employee_id)


@router.get("/{thread_id}/preview", response_class=FileResponse)
def preview(thread_id: str, p: Signed, request: Request) -> FileResponse:
    _reader(p)
    _ours(request, thread_id)
    st = _graph(request).get_state({"configurable": {"thread_id": thread_id}}).values
    pv = st.get("preview") or {}
    f = _inside(request, pv.get("path"))
    if hashlib.sha256(f.read_bytes()).hexdigest() != pv.get("sha256"):
        raise ApiError(409, "the preview changed since the draft was made", slug="preview_changed")
    return FileResponse(f, media_type=PPTX, filename=f"{thread_id.replace(':', '_')}_preview.pptx")


@router.get("/{thread_id}/deck", response_class=FileResponse)
def deck(thread_id: str, p: Signed, request: Request) -> FileResponse:
    _reader(p)
    _ours(request, thread_id)
    st = _graph(request).get_state({"configurable": {"thread_id": thread_id}}).values
    folder = (st.get("published") or {}).get("folder")
    f = _inside(request, str(Path(folder) / "deck.pptx") if folder else None)
    audit.record(employee_id=p.employee_id, resource_type="pack", resource_id=thread_id, action="download",
                 decision="allowed", request_id=request_id(request))
    return FileResponse(f, media_type=PPTX, filename=f"PortPilot_{wp.REPORT_YEAR}-W{st['report_week']:02d}.pptx")


def _decidable(thread_id: str, p: Principal, request: Request, action: str = "decide"):
    """(graph with models, config, the run's identity, state values) of a pack this approver may decide now."""
    _reader(p)
    _ours(request, thread_id)
    ok, why = wp.approver_check(p.employee_id)
    if not ok:
        audit.record(employee_id=p.employee_id, resource_type="pack", resource_id=thread_id, action=action,
                     decision="denied", request_id=request_id(request), detail={"why": why})
        raise ApiError(403, why, slug="not_allowed")
    g = _graph(request, with_models=True)
    cfg: Any = {"configurable": {"thread_id": thread_id}}
    snap = g.get_state(cfg)
    if not snap.values:
        raise ApiError(404, "no such pack", slug="not_found")
    if not snap.interrupts:
        raise ApiError(409, f"the pack is not waiting for a decision (status {snap.values.get('status')})",
                       slug="not_waiting")
    run_as = next((dict(h.metadata or {})["run_as"] for h in g.get_state_history(cfg)
                   if dict(h.metadata or {}).get("run_as")), None)
    if run_as is None:
        raise ApiError(409, "the pack has no run identity in its checkpoints", slug="no_run_identity")
    return g, cfg, int(str(run_as)), snap.values


def _accepted(request: Request, run: runs.Run, thread_id: str) -> RunAccepted:
    base = str(request.url_for("run_events", run_id=run.id).path).removesuffix("/events")
    return RunAccepted(run_id=run.id, thread_id=thread_id, events_url=f"{base}/events", run_url=base)


@router.post("/{thread_id}/decision", response_model=RunAccepted, status_code=202)
def decide(thread_id: str, body: DirectDecisionIn, p: Signed, request: Request) -> RunAccepted:
    g, cfg, run_as_id, _ = _decidable(thread_id, p, request)
    require_review(g, cfg, body.draft_sha)
    decision = {"decision": body.decision, "approver_employee_id": p.employee_id, "comment": body.comment,
                **body.changes()}
    rid, approver = request_id(request), p.employee_id

    def work(run: runs.Run) -> dict:
        ctx = context.RunContext(context.load_user(run_as_id), check_active=run.check_active)
        events = RunEvents(run, set(), PACK_NODES)
        with runs.thread_lock(thread_id), tracing.trace(thread_id, entry="api:pack_decision", run_as=run_as_id,
                                                        launched_by="api"):
            run.check_active()
            require_review(g, cfg, body.draft_sha)
            run_cfg: Any = {**cfg, "callbacks": [events]}
            for _ in g.stream(Command(resume=decision), run_cfg, context=ctx,
                              stream_mode="updates", durability="sync"):
                pass
        out = view(g, thread_id)
        if out["decisions"]:
            run.emit("approval_needed", {"thread_id": thread_id, "decisions": out["decisions"]})
        audit.record(employee_id=approver, resource_type="pack", resource_id=thread_id, trace_id=thread_id,
                     action="decide", decision="allowed", request_id=rid,
                     detail={"decision": body.decision, "status": out["status"],
                             **{k: len(v) if isinstance(v, list) else 1 for k, v in body.changes().items()}})
        return _result(thread_id, out["status"], None, out["validator_problems"], 0)

    run = request.app.state.runner.submit(p.employee_id, "pack_decision", work, thread_id=thread_id)
    return _accepted(request, run, thread_id)


# --- the manager's request in words (approver-request plan §2b, owner R2: understood first, applied on confirm) ----

class RequestIn(Strict):
    request: str = Field(min_length=3, max_length=ar.MAX_REQUEST_CHARS)


class ProposalIn(Strict):
    """The proposal as the request run returned it. Re-checked here and by the graph: a changed proposal can only
    hold what `POST /decision` accepts from this approver anyway."""
    understood: str = Field(min_length=1, max_length=ar.MAX_UNDERSTOOD_CHARS)
    steps: list[DecisionIn] = Field(min_length=1, max_length=3)
    draft_sha: str = Field(pattern=r"^[0-9a-f]{16}$")
    reread_text: bool = False


class ConfirmIn(Strict):
    request: str = Field(min_length=3, max_length=ar.MAX_REQUEST_CHARS)
    proposal: ProposalIn
    comment: str | None = Field(default=None, max_length=500)


def _result(thread_id: str, status: str, answer: dict | None, problems: list, calls: int) -> dict:
    # The common answer contract carries readable strings; PackView retains the full structured problems.
    messages = [f"{p.get('rule', 'validation')}: {p.get('message', '')}" if isinstance(p, dict) else str(p)
                for p in problems]
    return {"thread": thread_id, "status": status, "answer": answer, "not_permitted": [], "evidence": {},
            "problems": messages, "stop_reason": None, "model_calls": calls, "cached": 0}


@router.post("/{thread_id}/request", response_model=RunAccepted, status_code=202)
def read_request(thread_id: str, body: RequestIn, p: Signed, request: Request) -> RunAccepted:
    """One model call reads the request on the waiting draft; the run's `answer` is the proposal (what was understood,
    the steps, or an ask-back). Nothing is applied."""
    _, _, _, st = _decidable(thread_id, p, request, action="request")
    make_roles, rid, who = request.app.state.roles_factory, request_id(request), p.employee_id

    def work(run: runs.Run) -> dict:
        with tracing.trace(thread_id, entry="api:pack_request", run_as=who, launched_by="api"):
            prop = ar.propose(body.request, st, make_roles())
        # the proposal rides in the `answer` event (no new event: ADR-064's contract unchanged)
        audit.record(employee_id=who, resource_type="pack", resource_id=thread_id, trace_id=thread_id,
                     action="request", decision="allowed", request_id=rid,
                     detail={"steps": [s["decision"] for s in prop.steps], "ask_back": bool(prop.ask_back)})
        return _result(thread_id, "ask_back" if prop.ask_back else "proposed", prop.as_dict(), [], prop.model_calls)

    run = request.app.state.runner.submit(p.employee_id, "pack_request", work, thread_id=thread_id)
    return _accepted(request, run, thread_id)


@router.post("/{thread_id}/request/confirm", response_model=RunAccepted, status_code=202)
def confirm_request(thread_id: str, body: ConfirmIn, p: Signed, request: Request) -> RunAccepted:
    """Apply a proposal the manager confirmed: each step a decision on the waiting pack (a revise first, then the
    wording on the new draft); 409 when the pack no longer waits on the draft the request was read on."""
    g, cfg, run_as_id, st = _decidable(thread_id, p, request, action="request_confirm")
    if ar.draft_sha(st) != body.proposal.draft_sha:
        raise ApiError(409, "the draft changed since the request was read: send the request again", slug="stale")
    prop = ar.Proposal(understood=body.proposal.understood, draft_sha=body.proposal.draft_sha,
                       reread_text=body.proposal.reread_text,
                       steps=[{"decision": s.decision, **s.changes()} for s in body.proposal.steps])
    make_roles, rid, who = request.app.state.roles_factory, request_id(request), p.employee_id

    def work(run: runs.Run) -> dict:
        ctx = context.RunContext(context.load_user(run_as_id), check_active=run.check_active)
        events = RunEvents(run, set(), PACK_NODES)
        with runs.thread_lock(thread_id), tracing.trace(thread_id, entry="api:pack_request_confirm",
                                                        run_as=run_as_id, launched_by="api"):
            run.check_active()
            require_review(g, cfg, body.proposal.draft_sha)
            out = ar.apply(g, cfg, ctx, prop, body.request, who, make_roles(), comment=body.comment,
                           callbacks=[events])
        now = view(g, thread_id)
        if now["decisions"]:
            run.emit("approval_needed", {"thread_id": thread_id, "decisions": now["decisions"]})
        audit.record(employee_id=who, resource_type="pack", resource_id=thread_id, trace_id=thread_id,
                     action="request_confirm", decision="allowed", request_id=rid,
                     detail={"result": out["status"], "outcomes": [o["outcome"] for o in out["outcomes"]]})
        return _result(thread_id, now["status"] or out["status"], out, now["validator_problems"], out["model_calls"])

    run = request.app.state.runner.submit(p.employee_id, "pack_decision", work, thread_id=thread_id)
    return _accepted(request, run, thread_id)


# --- the dashboard's "this week's pack" (approver-request plan §2c, owner R1) --------------------------------------

dashboard = APIRouter(prefix="/finance", tags=["finance"])


class PackDashboard(Strict):
    """The published pack of a week as the dashboard shows it: the approved summary (the deck's slide 2) and its two
    charts drawn from the same `finance` rows, as the asker (RBAC in the tool)."""
    week: int
    thread_id: str
    approved_at: str | None
    approver_employee_id: int | None
    summary: list[str]
    charts: list[gm.ViewSpec]
    degraded: bool
    publication_sync: Literal["synced", "pending", "not_required", "unknown", "superseded"] = "unknown"


@dashboard.get("/pack", response_model=PackDashboard)
def week_pack(p: Signed, request: Request, week: int = Query(ge=1, le=52)) -> dict:
    _reader(p)
    folder = Path(request.app.state.reports_dir) / f"{wp.REPORT_YEAR}-W{week:02d}"
    manifest, folder = publications.current(folder)
    f = _inside(request, str(folder / "run.json"))
    run = json.loads(f.read_text(encoding="utf-8"))
    if "summary" not in run:
        raise ApiError(404, f"week {week}'s pack was published before the dashboard summary existed", slug="not_found")
    try:
        specs = views.pack_views(p.user, week, run.get("charts"))
    except views.ViewUnavailable as exc:
        raise ApiError(403 if exc.status == "not_permitted" else 404, str(exc), slug="not_permitted"
                       if exc.status == "not_permitted" else "not_found") from None
    audit.record(employee_id=p.employee_id, resource_type="pack", resource_id=run["thread_id"], action="read",
                 decision="allowed", request_id=request_id(request), detail={"week": week, "view": "dashboard"})
    approved = run.get("approved") or {}
    return {"week": week, "thread_id": run["thread_id"], "approved_at": approved.get("at"),
            "approver_employee_id": approved.get("approver_employee_id"), "summary": run["summary"],
            "charts": specs, "degraded": bool(run.get("degraded")),
            "publication_sync": manifest["db_sync"]["status"] if manifest else "unknown"}
