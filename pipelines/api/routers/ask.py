"""Ask the supervisor (plan §3.2): conversations, questions as runs, the run's events over SSE, stored answers.

A question runs exactly as `Ask.py ask` does — `sv.route` (refused tools dropped before any model sees them),
`sv.ask` on a PostgresSaver thread `ask:<employee>:<as_of>:<n>`, one LangSmith trace with the same tags — but in the
run executor (202 at once), with fresh roles per run (one run's stopped model never stops the next) and an event
callback that reports node and tool **names** only. Conversation memory (§6a) joins in P6m, uploads in P5.
"""
import asyncio
import json
import time
from datetime import timezone
from typing import Annotated, Any, cast

from fastapi import APIRouter, Header, Request
from fastapi.sse import KEEPALIVE_COMMENT, EventSourceResponse, format_sse_event
from langchain_core.callbacks import BaseCallbackHandler

from pipelines.agents import checkpointer, memory, scheduling, tracing
from pipelines.agents.graphs import supervisor as sv
from pipelines.agents.tools import context
from pipelines.api import audit, runs, store
from pipelines.api.auth import Signed
from pipelines.api.errors import ApiError, request_id
from pipelines.api.schemas import (RUN_EVENT, AnswerData, ConversationDetail, FailedData, ConversationOut, QuestionDetail, QuestionIn,
                                   RunAccepted, RunEventSchema, RunOut, ThreadRow, TurnOut)

router = APIRouter(tags=["ask"])
HEARTBEAT_S = 15
POLL_S = 0.2
NODES = frozenset({"model", "tools"})            # the supervisor's own nodes; middleware and subgraph nodes not shown


class RunEvents(BaseCallbackHandler):
    """LangChain callbacks → the run's `node` / `tool_called` events: names on an allowlist, nothing else."""
    raise_error = True  # cooperative expiry stops subsequent graph/model/tool starts

    def __init__(self, run: runs.Run, tools: set[str], nodes: frozenset[str] = NODES):
        self.run, self.tools, self.nodes = run, tools, nodes
        self._open: dict = {}

    def on_chain_start(self, serialized, inputs, *, run_id, metadata=None, **kw):
        self.run.check_active()
        node = (metadata or {}).get("langgraph_node")
        if node in self.nodes and kw.get("name") == node:
            self._open[run_id] = node
            self.run.emit("node", {"name": node, "phase": "start"})

    def on_chain_end(self, outputs, *, run_id, **kw):
        node = self._open.pop(run_id, None)
        if node:
            self.run.emit("node", {"name": node, "phase": "end"})

    def on_chain_error(self, error, *, run_id, **kw):
        self._open.pop(run_id, None)

    def on_tool_start(self, serialized, input_str, *, run_id, **kw):
        self.run.check_active()
        name = (serialized or {}).get("name") or kw.get("name")
        if name in self.tools:
            self.run.emit("tool_called", {"name": name})


def _reader(request: Request):
    """The supervisor on the checkpointer, to read stored answers (no model is ever called through it)."""
    app = request.app
    if getattr(app.state, "ask_reader", None) is None:
        app.state.ask_reader = sv.build_graph(None, checkpointer.saver())
    return app.state.ask_reader


def conversation_for(conversation_id: str, p, *, write: bool) -> dict:
    """The conversation if the caller may use it: its owner always; the CEO may read, never continue (§6a.3)."""
    with store.pool().connection() as conn:
        row = cast(Any, conn.execute("SELECT conversation_id::text AS conversation_id, employee_id, created_at, "
                                     "last_turn_at, closed_at FROM conversations WHERE conversation_id::text = %s",
                                     (conversation_id,)).fetchone())
    if row is None or (row["employee_id"] != p.employee_id and (write or p.user.role != "ceo")):
        raise ApiError(404, "no such conversation", slug="not_found")
    if write and row["closed_at"] is not None:
        raise ApiError(409, "the conversation is closed", slug="closed")
    return dict(row)


# --- conversations ------------------------------------------------------------------------------------------------
@router.post("/conversations", response_model=ConversationOut, status_code=201)
def open_conversation(p: Signed) -> ConversationOut:
    with store.pool().connection() as conn:
        row = cast(Any, conn.execute("INSERT INTO conversations (employee_id) VALUES (%s) RETURNING "
                                     "conversation_id::text AS conversation_id, employee_id, created_at, last_turn_at, "
                                     "closed_at", (p.employee_id,)).fetchone())
    return ConversationOut(**row)


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(p: Signed) -> list[ConversationOut]:
    everyone = p.user.role == "ceo"
    with store.pool().connection() as conn:
        rows = conn.execute("SELECT conversation_id::text AS conversation_id, employee_id, created_at, last_turn_at, "
                            "closed_at FROM conversations WHERE %s OR employee_id = %s ORDER BY created_at DESC "
                            "LIMIT 200", (everyone, p.employee_id)).fetchall()
    return [ConversationOut(**cast(Any, r)) for r in rows]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str, p: Signed) -> ConversationDetail:
    conv = conversation_for(conversation_id, p, write=False)
    with store.pool().connection() as conn:
        turns = conn.execute("SELECT turn_no, question, standalone_question, resolved_by, lang, as_of, status, "
                             "thread_id FROM conversation_turns WHERE conversation_id::text = %s ORDER BY turn_no",
                             (conversation_id,)).fetchall()
    return ConversationDetail(**conv, turns=[TurnOut(**cast(Any, t)) for t in turns])


@router.delete("/conversations/{conversation_id}", status_code=204)
def close_conversation(conversation_id: str, p: Signed, request: Request) -> None:
    conversation_for(conversation_id, p, write=True)
    with store.pool().connection() as conn, conn.transaction():
        conn.execute("DELETE FROM conversation_turns WHERE conversation_id::text = %s", (conversation_id,))
        conn.execute("UPDATE conversations SET closed_at = now() WHERE conversation_id::text = %s", (conversation_id,))
    request.app.state.uploads.close(conversation_id)                 # its uploads leave the memory at once
    audit.record(employee_id=p.employee_id, resource_type="conversation", resource_id=conversation_id,
                 action="close", decision="allowed", request_id=request_id(request))


# --- a question = a run -------------------------------------------------------------------------------------------
def _save_turn(conversation_id: str, tid: str, res, frame: dict, answer_masked: str | None,
               refused: list | None = None) -> None:
    """The turn's memory (§6a.1): its standalone form, how it was resolved, the code-built frame, the masked answer."""
    with store.pool().connection() as conn:
        conn.execute("UPDATE conversation_turns SET standalone_question = %s, resolved_by = %s, frame = %s::jsonb, "
                     "answer_masked = %s, refused = %s WHERE conversation_id::text = %s AND thread_id = %s",
                     (res.standalone if res.by in ("code", "model") else None, res.by,
                      json.dumps(frame, default=str), answer_masked, refused or [], conversation_id, tid))



@router.post("/conversations/{conversation_id}/questions", response_model=RunAccepted, status_code=202)
def ask_question(conversation_id: str, body: QuestionIn, p: Signed, request: Request) -> RunAccepted:
    conversation_for(conversation_id, p, write=True)
    as_of = body.as_of.replace(tzinfo=body.as_of.tzinfo or timezone.utc) if body.as_of else context.DATA_AS_OF
    try:
        as_of = context.RunContext(p.user, as_of=as_of).as_of            # refuses a clock past the data
    except ValueError as exc:
        raise ApiError(422, str(exc), slug="invalid_request") from None
    lang = body.lang or sv.detect_lang(body.question)
    user, question, rid = p.user, body.question, request_id(request)
    runner: runs.Runner = request.app.state.runner
    make_roles = request.app.state.roles_factory
    sessions = request.app.state.uploads
    tid = runner.reserve_thread(lambda: sv.new_thread_id(checkpointer.pool(), user.employee_id, as_of))

    def work(run: runs.Run) -> dict:
        with store.pool().connection() as conn:
            conn.execute("INSERT INTO conversation_turns (conversation_id, turn_no, question, resolved_by, lang, as_of, "
                         "thread_id) SELECT %s::uuid, coalesce(max(turn_no), 0) + 1, %s, 'none', %s, %s, %s FROM "
                         "conversation_turns WHERE conversation_id::text = %s",
                         (conversation_id, question, lang, as_of, tid, conversation_id))
            conn.execute("UPDATE conversations SET last_turn_at = now() WHERE conversation_id::text = %s",
                         (conversation_id,))
            past = conn.execute("SELECT question, coalesce(standalone_question, question) AS standalone, frame FROM "
                                "conversation_turns WHERE conversation_id::text = %s AND thread_id <> %s AND status "
                                "NOT IN ('clarify', 'failed', 'not_permitted') ORDER BY turn_no DESC LIMIT %s",
                                (conversation_id, tid, memory.HISTORY)).fetchall()
        history = [memory.Turn(h["question"], h["standalone"], h["frame"] or {})
                   for h in (cast(dict, x) for x in reversed(past))]          # dict_row pool
        roles = make_roles()
        res = memory.resolve(question, lang, history, rewrite=memory.model_rewrite(roles))
        if res.by == "clarify":                    # §6a.2: ask back, no tool runs
            _save_turn(conversation_id, tid, res, {}, None)
            return {"thread": None, "status": "clarify", "answer": res.clarify, "not_permitted": [], "evidence": {},
                    "problems": [], "stop_reason": None, "model_calls": 0, "cached": 0}
        if res.by != "none":
            run.emit("understood", {"standalone_question": res.standalone, "used_entities": res.used, "by": res.by})
        asked = res.standalone
        r = sv.route(asked, user)
        for t in r.refused:
            run.emit("tool_refused", {"name": t, "part": sv.REFUSED_PART.get(t, t)})
        saver = checkpointer.saver()
        g = sv.build_graph(roles, saver, saver=saver, pool=checkpointer.pool())
        tags = ("graph:supervisor", f"lang:{lang}", *(["refused"] if r.refused else []),
                *[f"refused:{t}" for t in r.refused], *([f"memory:{res.by}"] if res.by != "none" else []))
        with runs.thread_lock(tid), tracing.trace(tid, entry="api:ask", run_as=user.employee_id, launched_by="api",
                                                  extra_tags=tags):
            run.check_active()
            if g.get_state({"configurable": {"thread_id": tid}}).values:
                raise ApiError(409, "this question thread already exists; retry", slug="thread_exists")
            st = sv.ask(g, asked, user, lang, as_of, thread=tid, metadata={"trigger": "api"},
                        callbacks=[RunEvents(run, set(r.tools))],
                        session=sessions.get(conversation_id, user.employee_id, create=False))
        _save_turn(conversation_id, tid, res, memory.frame_of(st, asked),
                   memory.mask((st.get("answer") or {}).get("answer")), st.get("refused") or [])
        out = sv.answer_summary(st)
        audit.record(employee_id=user.employee_id, resource_type="question", resource_id=tid, trace_id=tid,
                     action="ask", decision="allowed", request_id=rid,
                     detail={"status": out["status"], "conversation_id": conversation_id,
                             "model_calls": out["model_calls"]})
        for t in r.refused:
            audit.record(employee_id=user.employee_id, resource_type="tool", resource_id=t, trace_id=tid,
                         action="refused_part", decision="denied", request_id=rid)
        return out

    def on_finish(state: str, result: dict | None) -> None:
        """Before `done` is sent (D-F2): a follow-up asked at once sees this turn in its history (a NULL status
        would drop it: `NULL NOT IN (…)` is not true)."""
        status = (result or {}).get("status") if state == "done" else "failed"
        with store.pool().connection() as conn:
            conn.execute("UPDATE conversation_turns SET status = %s WHERE conversation_id::text = %s AND thread_id = %s",
                         (status, conversation_id, tid))

    run = runner.submit(user.employee_id, "ask", work, thread_id=tid, conversation_id=conversation_id,
                        on_finish=on_finish)
    base = str(request.url_for("run_events", run_id=run.id).path).removesuffix("/events")
    return RunAccepted(run_id=run.id, thread_id=tid, events_url=f"{base}/events", run_url=base)


# --- runs ---------------------------------------------------------------------------------------------------------
def _run_out(run: runs.Run) -> RunOut:
    return RunOut(run_id=run.id, kind=run.kind, state=cast(Any, run.state), thread_id=run.thread_id,
                  conversation_id=run.conversation_id, created_at=run.created_at, finished_at=run.finished_at,
                  result=AnswerData.model_validate(run.result) if run.result is not None else None,
                  error=FailedData.model_validate(run.error) if run.error is not None else None,
                  events=[RUN_EVENT.validate_python({"id": e.id, "event": e.event, "data": e.data})
                          for e in run.since(0)])


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, p: Signed, request: Request) -> RunOut:
    return _run_out(request.app.state.runner.get(run_id, p.employee_id))


# no `response_class=EventSourceResponse`: with it FastAPI 0.150 expects the route itself to be a generator of events
@router.get("/runs/{run_id}/events", name="run_events",
            responses={200: {"model": RunEventSchema, "content": {"text/event-stream": {}},
                             "description": "the run's events as SSE; each `data:` line is a RunEventSchema's data"}})
async def run_events(run_id: str, p: Signed, request: Request,
                     last_event_id: Annotated[str | None, Header()] = None) -> EventSourceResponse:
    run: runs.Run = request.app.state.runner.get(run_id, p.employee_id)
    start = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0

    async def stream():
        last, beat = start, time.monotonic()
        while True:
            for e in run.since(last):
                yield format_sse_event(data_str=json.dumps(e.data, ensure_ascii=False, default=str), event=e.event,
                                       id=str(e.id))
                last, beat = e.id, time.monotonic()
            if run.finished and not run.since(last):
                return
            if await request.is_disconnected():
                return
            if time.monotonic() - beat >= HEARTBEAT_S:
                yield KEEPALIVE_COMMENT
                beat = time.monotonic()
            await asyncio.sleep(POLL_S)
    return EventSourceResponse(stream(), headers={"X-Accel-Buffering": "no"})


# --- stored answers -----------------------------------------------------------------------------------------------
@router.get("/questions", response_model=list[ThreadRow])
def list_questions(p: Signed, request: Request) -> list[dict]:
    prefix = sv.THREAD_PREFIX if p.user.role == "ceo" else f"{sv.THREAD_PREFIX}{p.employee_id}:"
    infos = scheduling.describe_ask(_reader(request), checkpointer.pool(), prefix)
    return [{"thread_id": i.thread_id, "state": i.state, "status": i.status, "last_at": i.last_at} for i in infos]


@router.get("/questions/{thread_id}", response_model=QuestionDetail)
def get_question(thread_id: str, p: Signed, request: Request) -> dict:
    if not sv.can_read_thread(p.user, thread_id):
        audit.record(employee_id=p.employee_id, resource_type="question", resource_id=thread_id, action="read",
                     decision="denied", request_id=request_id(request))
        raise ApiError(404, "no such question", slug="not_found")
    st = _reader(request).get_state({"configurable": {"thread_id": thread_id}}).values
    if not st:
        raise ApiError(404, "no such question", slug="not_found")
    audit.record(employee_id=p.employee_id, resource_type="question", resource_id=thread_id, action="read",
                 decision="allowed", request_id=request_id(request))
    return {**sv.answer_summary({**st, "thread_id": thread_id}), "question": st.get("question")}
