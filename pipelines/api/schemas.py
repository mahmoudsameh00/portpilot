"""Request and response models (plan §2): the OpenAPI schema the frontend's typed client is generated from
(ADR-060 (4)). Request models forbid unknown fields (plan §9, API3): no employee id, role or dataset is accepted from
a client."""
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, TypeAdapter

from pipelines.api import config

# --- the event contract (plan §5; ADR-060 amendment 1 (b)) ----------------------------------------------------------
# every event a run may emit and the only fields it may carry: never the model's reasoning, a prompt, a tool's
# arguments or rows, or an unchecked number
ANSWER_FIELDS = frozenset({"thread", "status", "answer", "not_permitted", "evidence", "problems", "stop_reason",
                           "model_calls", "cached",
                           "view",        # approver-additions plan §2d: a drawn view (every value a view field)
                           "numbers"})    # Frontend plan D-FE-1: where each bound number sits in `answer`
EVENT_FIELDS: dict[str, frozenset[str]] = {
    "queued": frozenset({"position"}),
    "started": frozenset({"thread_id", "graph"}),
    "understood": frozenset({"standalone_question", "used_entities", "by"}),
    "node": frozenset({"name", "phase"}),
    "tool_called": frozenset({"name"}),
    "tool_refused": frozenset({"name", "part"}),
    "approval_needed": frozenset({"thread_id", "decisions"}),
    "answer": ANSWER_FIELDS,
    "done": frozenset({"status"}),
    "failed": frozenset({"type", "status", "detail"}),
}


class ContractError(RuntimeError):
    """An event outside the contract: a bug in the API, answered as a 500 (never sent)."""


def check_event(event: str, data: dict) -> None:
    allowed = EVENT_FIELDS.get(event)
    if allowed is None or not set(data) <= allowed:
        raise ContractError(f"event {event!r} with fields {sorted(data)} is outside the contract")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginIn(Strict):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class Products(BaseModel):
    """What this employee may use — computed from the same RBAC the tools apply (ADR-006), never decided in the UI."""
    ask: bool = Field(description="ask the supervisor (every employee; the refused parts are named in the answer)")
    packs_read: bool = Field(description="read the weekly finance packs (level 2 / Finance, ADR-006)")
    packs_decide: bool = Field(description="approve / edit / reject a pack (a Finance manager or the CEO)")
    route_advice: bool
    voyage_watch: bool
    arrival_advice: bool = Field(default=False, description="Just-in-Time arrival advice for a vessel at sea (ADR-070): "
                                                            "the graph's own tool access (ADR-006)")
    uploads: bool = Field(description="upload a document into a conversation")


class Me(BaseModel):
    employee_id: int
    role: str
    department: str
    ceiling: int = Field(description="the highest sensitivity level this role reads in any department")
    tools: list[str] = Field(description="the supervisor's data tools this employee may use")
    products: Products


class TokenOut(BaseModel):
    token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    me: Me


class QuestionIn(Strict):
    question: str = Field(min_length=1, max_length=config.QUESTION_MAX_CHARS)
    lang: Literal["en", "ar"] | None = Field(default=None, description="detected from the question when omitted")
    as_of: datetime | None = Field(default=None, description="the clock (UTC); default and maximum: the data's as-of")


class RunAccepted(BaseModel):
    run_id: str
    thread_id: str | None
    events_url: str = Field(description="SSE stream of the run's events; read it with fetch (it needs the token)")
    run_url: str


class Open(BaseModel):
    """A typed record whose producer (a graph, a tool) may add fields: the named ones are guaranteed, the rest pass
    through (the frontend reads only the named ones)."""
    model_config = ConfigDict(extra="allow")


# --- the event contract as types (Frontend plan F0: the browser validates every event against these) ---------------
class NumberSpan(BaseModel):
    """Where one bound number sits in a rendered text (Frontend plan D-FE-1): offsets in UTF-16 code units."""
    text: str
    start: int
    end: int
    evidence_id: str
    field: str
    source: str | None = Field(description="the view / tool the value was read from, e.g. finance.kpi_weekly")
    filter: str | None = Field(description="the filter that selected the row, e.g. report_week = 23")
    row: int | None = Field(description="the row index in the evidence; None = a result-level field")


class EvidenceRef(BaseModel):
    tool: str | None
    status: str | None
    source: str | None


class AnswerData(Open):
    """The `answer` event's data, `RunOut.result` and `GET /questions/{thread_id}` (supervisor.answer_summary).
    `answer` is the rendered text for a question, the result object for route advice / a watch run, the caption for a
    view; `numbers` locate the bound numbers in a text answer."""
    thread: str | None = None
    status: str | None
    answer: str | dict[str, Any] | None = None
    not_permitted: list[str] = Field(default_factory=list)
    evidence: dict[str, EvidenceRef] = Field(default_factory=dict)
    problems: list[str] = Field(default_factory=list)
    stop_reason: str | None = None
    model_calls: int = 0
    cached: int = 0
    view: dict[str, Any] | None = Field(default=None, description="a ViewSpec when the run drew a view")
    numbers: list[NumberSpan] = Field(default_factory=list)


class QueuedData(BaseModel):
    position: int


class StartedData(BaseModel):
    thread_id: str | None
    graph: str


class UnderstoodData(BaseModel):
    standalone_question: str
    used_entities: dict[str, list[Any]]
    by: str = Field(description="code or model")


class NodeData(BaseModel):
    name: str
    phase: Literal["start", "end"]


class ToolCalledData(BaseModel):
    name: str


class ToolRefusedData(BaseModel):
    name: str
    part: str = Field(description="the refused part, in words, for the answer card")


class ApprovalNeededData(BaseModel):
    thread_id: str
    decisions: list[str]


class DoneData(BaseModel):
    status: str


class FailedData(BaseModel):
    type: str
    status: int
    detail: str


class _Event(BaseModel):
    id: int


class QueuedEvent(_Event):
    event: Literal["queued"]
    data: QueuedData


class StartedEvent(_Event):
    event: Literal["started"]
    data: StartedData


class UnderstoodEvent(_Event):
    event: Literal["understood"]
    data: UnderstoodData


class NodeEvent(_Event):
    event: Literal["node"]
    data: NodeData


class ToolCalledEvent(_Event):
    event: Literal["tool_called"]
    data: ToolCalledData


class ToolRefusedEvent(_Event):
    event: Literal["tool_refused"]
    data: ToolRefusedData


class ApprovalNeededEvent(_Event):
    event: Literal["approval_needed"]
    data: ApprovalNeededData


class AnswerEvent(_Event):
    event: Literal["answer"]
    data: AnswerData


class DoneEvent(_Event):
    event: Literal["done"]
    data: DoneData


class FailedEvent(_Event):
    event: Literal["failed"]
    data: FailedData


RunEvent = Annotated[QueuedEvent | StartedEvent | UnderstoodEvent | NodeEvent | ToolCalledEvent | ToolRefusedEvent
                     | ApprovalNeededEvent | AnswerEvent | DoneEvent | FailedEvent, Field(discriminator="event")]
RUN_EVENT: TypeAdapter[Any] = TypeAdapter(RunEvent)


class RunEventSchema(RootModel[RunEvent]):
    """One server-sent event of GET /runs/{run_id}/events: `id:` = id, `event:` = event, `data:` = data as JSON."""


class RunOut(BaseModel):
    run_id: str
    kind: str
    state: Literal["queued", "running", "done", "failed"]
    thread_id: str | None
    conversation_id: str | None
    created_at: datetime
    finished_at: datetime | None
    result: AnswerData | None = Field(description="the answer event's data when done")
    error: FailedData | None
    events: list[RunEvent]


# --- reads (Frontend plan F0: every 200 typed) ------------------------------------------------------------------------
class ThreadRow(BaseModel):
    thread_id: str
    state: str = Field(description="ended | stalled | pending")
    status: str | None
    last_at: datetime


class PackRow(ThreadRow):
    week: int
    attempt: int


class WatchRunRow(ThreadRow):
    """A saved watch run in the operational run history."""


class PackAllowed(BaseModel):
    """What the approver may still do on this pack (the graph's rules, so the UI never hard-codes them)."""
    decide: bool = Field(description="this employee may decide, and the pack waits for a decision")
    addition_slides: list[int] = Field(description="slides that accept an approver's bullet (approver plan D3)")
    max_additions: int
    max_chart_changes: int
    max_analysis_edits: int
    max_steer_chars: int
    revise_left: int = Field(description="revisions left before only approve / edit / reject remain")


class PackView(Open):
    """`Weekly_pack.py show` as data + what the approver may still do and the charts the deck draws."""
    thread_id: str
    draft_sha: str = Field(description="Review version; send unchanged with a direct decision")
    status: str | None
    next: list[str]
    week: int | None
    readiness: list[Any]
    validator_problems: list[Any]
    degraded: Any = None
    draft: dict[str, Any] | None = Field(description=(
        "the draft with its slots filled; a bullet or slide title code wrote after the Writer's rewrites failed has "
        "origin 'code', an approver's edit has edited true, and `removed` lists the Writer texts code took out "
        "({slide, text, by: code | fallback, why}) — shown on their slide (targeted-revise plan B4)"))
    has_preview: bool
    decisions: list[str]
    approval_log: list[dict[str, Any]]
    form_fixes: int
    published: bool
    publication_sync: Literal["synced", "pending", "not_required", "unknown", "superseded"] = "unknown"
    insight: dict[str, Any] | None = None
    charts: dict[str, Any] = Field(default_factory=dict)
    redrafted: bool = False
    redrafted_slides: list[int] = Field(default_factory=list, description=(
        "the slides the last revise re-drafted; every other slide, the additions and the chart variants were kept "
        "(targeted-revise plan A5)"))
    revision: Any = None
    fallback_share: float | None = Field(default=None, description=(
        "of the model calls answered for this pack, the share a fallback model answered (Model flexibility plan W10)"))
    allowed: PackAllowed
    charts_drawn: dict[str, Any] = Field(default_factory=dict, description="the series each chart slide draws "
                                                                           "(render.build_spec), by slide")


class ApprovalReport(Open):
    packs_decided: int
    published: int
    rejected: int
    packs_edited: int
    edit_rate: float | None
    decisions: dict[str, int]
    edited_slides: dict[str, int]
    changes: dict[str, int]
    form_fixes: dict[str, int]
    degraded: int
    threads: list[str]


class QuestionDetail(AnswerData):
    question: str | None


class RouteNumbers(BaseModel):
    headline: list[NumberSpan] = Field(default_factory=list)
    reasons: list[list[NumberSpan]] = Field(default_factory=list)
    risks: list[list[NumberSpan]] = Field(default_factory=list)


class RouteAdviceDetail(Open):
    thread_id: str
    status: str | None
    recommendation: Literal["suez", "cape"] | None = None
    headline: str | None = None
    comparison: list[dict[str, Any]] | None = None
    reasons: list[str] | None = None
    risks: list[str] | None = None
    assumptions: list[str] | None = None
    problems: list[str] | None = None
    sources: list[str] = Field(default_factory=list)
    model_calls: int = 0
    cached: int = 0
    numbers: RouteNumbers = Field(default_factory=RouteNumbers)


class ArrivalOption(Open):
    """One computed speed option of `tools/arrival.py` (code, never the model): keep / jit / floor / catch_up / cape."""
    option: Literal["keep", "jit", "floor", "catch_up", "cape"]
    speed_kn: float | None = None
    arrival_utc: str | None = None
    arrives_by_rta: bool | None = None
    wait_h: float | None = None
    late_h: float | None = None
    fuel_t: float | None = None
    fuel_sdr: float | None = None
    total_sdr: float | None = None
    change_fuel_t: float | None = None
    change_total_sdr: float | None = None


class ArrivalAdvice(Open):
    """One arrival advice (ADR-070), as `arrival_advice.result_summary` gives it; numbers in the texts carry spans.
    `status` "error" = the watch could not run this advice (its reason in `problems`)."""
    status: str | None
    recommendation: Literal["keep", "jit", "floor", "catch_up", "cape"] | None = None
    headline: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict, description="the vessel, its destination, the RTA (and its "
                                                                     "source), the target, the situation")
    options: list[ArrivalOption] = Field(default_factory=list)
    reasons: list[str] | None = None
    risks: list[str] | None = None
    assumptions: list[str] | None = None
    problems: list[str] | None = None
    sources: list[str] = Field(default_factory=list)
    model_calls: int = 0
    cached: int = 0
    numbers: RouteNumbers = Field(default_factory=RouteNumbers)


class ArrivalAdviceDetail(ArrivalAdvice):
    """A stored arrival advice thread (`GET /arrival-advice/{thread}`)."""
    thread_id: str


class WatchEta(Open):
    """One vessel of the run's ETA table (rule R, `tools/eta.py`): the rule's ETA at the run's clock — never the voyage
    file's `arrival_ts` (the answer key, ADR-055)."""
    vessel_id: int
    vessel_name: str | None = None
    status: str | None = None
    destination: str | None = None
    next_port: str | None = None
    eta_utc: str | None = None
    eta_in_h: float | None = None
    distance_left_nm: float | None = None
    speed_kn: float | None = None
    suez_ahead: bool | None = None
    last_fix_ts: str | None = None
    note: str | None = None


class WatchRunDetail(BaseModel):
    thread_id: str
    status: str | None
    as_of: str | None = None
    fleet: dict[str, Any] = Field(default_factory=dict)
    headline: str | None = None
    items: list[str] = Field(default_factory=list)
    etas: list[WatchEta] = Field(default_factory=list, description="the run's ETA table, one row per watched vessel "
                                                                    "(D-FE-10: the web's ETA board)")


class WatchAlert(Open):
    alert_id: str
    kind: str = Field(description="weather | suez_traffic | rta_late | jit | customer (ADR-070: the rta_utc, "
                                  "rta_location and option fields ride along)")
    severity: str | None = None
    vessel_id: int | None = None
    vessel_name: str | None = None
    destination: str | None = None
    eta_utc: str | None = None
    reason: str | None = None
    customer_id: int | None = None
    advice: ArrivalAdvice | None = Field(default=None, description="a jit / rta_late alert's arrival advice, made by "
                                                                   "the same watch run (Arrival advice web plan)")


class WatchAlerts(BaseModel):
    status: Literal["ok", "no_data", "not_permitted"]
    note: str | None = None
    thread_id: str | None = None
    as_of: str | None = None
    headline: str | None = None
    alerts: list[WatchAlert] = Field(default_factory=list)
    of: int | None = Field(default=None, description="the run's alert count before the filters")


class ChartCatalogue(Open):
    """charts.catalogue(): the pack's chart variants and the views' kinds and options (approver plan Phase F)."""
    pack: dict[str, Any]
    views: dict[str, Any]


class PromotionOut(BaseModel):
    request_id: str
    status: Literal["requested"]


class ConversationOut(BaseModel):
    conversation_id: str
    employee_id: int
    created_at: datetime
    last_turn_at: datetime | None
    closed_at: datetime | None


class TurnOut(BaseModel):
    turn_no: int
    question: str
    standalone_question: str | None
    resolved_by: str
    lang: str
    as_of: datetime
    status: str | None
    thread_id: str | None


class ConversationDetail(ConversationOut):
    turns: list[TurnOut]


class Reason(BaseModel):
    code: str
    where: str
    message: str


class UploadOut(BaseModel):
    """The verdict on one upload (ADR-042): what the employee is told; never the document's text."""
    accepted: bool
    filename: str
    document_id: str | None
    document_code: str | None
    title: str | None
    chunks: int
    reasons: list[Reason] = Field(description="refusals: any one = not accepted")
    removed: list[Reason] = Field(description="sections the screening removed (the rest was accepted)")
    notes: list[Reason]
    message: str


class UploadSummary(BaseModel):
    document_id: str
    document_code: str
    title: str
    filename: str
    chunks: int
    removed: int


class PromotionIn(Strict):
    note: str = Field(default="", max_length=500)


class Component(BaseModel):
    name: str
    ok: bool


class Ready(BaseModel):
    status: Literal["ready", "degraded"]
    components: list[Component]
    llm_requests_today: dict[str, int] = Field(description="requests reserved today per model scope (counts only)")
