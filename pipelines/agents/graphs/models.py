"""Structured outputs of the `weekly_pack` graph (Agents plan §3 "Structured outputs", §5b P5-2, P5-4).

One class serves the LLM (`with_structured_output`), the graph state (stored as `model_dump(mode="json")`, so every
checkpoint is plain data), the Validator and the tests. Kept shallow — at most two levels of objects, `Literal`
instead of enums, no unions — because free providers support different JSON-schema subsets (ADR-045, bake-off T3).
Format rules live here (slide range, evidence-id shape, non-empty text); content rules (five summary bullets, every
number from a tool) belong to the Validator, so a broken draft comes back as a readable diff, not as a parse error.

Evidence ids name a tool result kept in the state: `kpi.<dataset>`, `audit.week`, `audit.ytd`,
`insight.<tool_call_id>`.
"""
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from pipelines.agents.deck import charts

EVIDENCE_ID = r"^(kpi|audit|insight|context)\.[A-Za-z0-9_.:-]+$"   # context.*: external-context plan
SLIDES = 10                                   # deck-style-guide: ten slides in a fixed order
# A slot may name a row ({kpi.category[LNG Carriers]:billed_sdr}); a Writer that copies the slot's head into
# evidence_ids writes "kpi.category[LNG Carriers]". The citation is the result, not its row, so code drops a trailing
# [row] before the check (D-EC-5, external-context plan Phase E: W16 failed twice on it). An id that is wrong for any
# other reason is still refused.
ROW_SUFFIX_RE = re.compile(r"\[[^\[\]{}]+\]$")


def norm_ids(ids: list[str]) -> list[str]:
    return [ROW_SUFFIX_RE.sub("", e) for e in ids]


class Cited(BaseModel):
    text: str = Field(min_length=1, description="one sentence; every number in it copied from the cited evidence")
    evidence_ids: list[str] = Field(default_factory=list,
                                    description="ids of the tool results the sentence's numbers come from")

    @model_validator(mode="after")
    def _ids(self):
        self.evidence_ids = norm_ids(self.evidence_ids)
        bad = [e for e in self.evidence_ids if not re.match(EVIDENCE_ID, e)]
        if bad:
            raise ValueError(f"evidence ids must look like kpi.weekly / audit.week / insight.<id> / context.<name>: {bad}")
        return self


# --- Insight ------------------------------------------------------------------------------------------------------

class Driver(BaseModel):
    vessel_category: str = Field(description="a category among the week's top 3 by |billed_wow_change_sdr|")
    direction: Literal["up", "down"] = Field(description="the sign of billed_wow_change_sdr (budget variance in week 1)")
    flagged_by_audit: bool = Field(description="true if an invoice of this category has an audit finding this week")
    explanation: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)


class InsightNotes(BaseModel):
    """What changed, by how much and why (skill `weekly-variance-analysis`), for the Report Writer."""
    summary: list[Cited] = Field(description="the 5 executive-summary bullets, in the skill's order")
    drivers: list[Driver] = Field(default_factory=list, description="at most 3")
    context: list[Cited] = Field(default_factory=list,
                                 description="external context (Suez transits, news, tariff rules), kept apart "
                                             "from PortPilot's numbers; 'context unavailable' when a tool said so")
    caveats: list[str] = Field(default_factory=list, description="warm-up week, flagged invoices, missing context")


# --- Deck draft -----------------------------------------------------------------------------------------------------

class SlideTitle(BaseModel):
    slide: int = Field(ge=1, le=SLIDES)
    title: str = Field(min_length=1, description="states the finding, not the topic")


class Bullet(Cited):
    slide: int = Field(ge=1, le=SLIDES, description="1 title … 10 sources, as in the deck style guide")


class DeckDraft(BaseModel):
    """The deck as text with number slots (Phase 6, §5c); `pipelines/agents/deck/render.py` renders it into the
    PortPilot PPTX template."""
    title: str = Field(min_length=1, description='"PortPilot Weekly Finance Pack — <week> — Draft for approval"')
    slide_titles: list[SlideTitle] = Field(description="one title per slide, slides 1 to 10")
    bullets: list[Bullet] = Field(description="every bullet of slides 2 to 9, in slide order")


class SlidesDraft(BaseModel):
    """A revise's re-draft of the named slides only (targeted-revise plan A2): code merges it into the deck the
    approver had, every other slide kept as it stands."""
    slide_titles: list[SlideTitle] = Field(description="one title for each slide you were asked to write")
    bullets: list[Bullet] = Field(description="the bullets of the slides you were asked to write, in slide order")


class Fix(BaseModel):
    target: Literal["bullet", "slide_title", "title"]
    index: int = Field(ge=0, description="bullet: its index in DeckDraft.bullets; slide_title: the slide number; "
                                         "title: 0")
    text: str = Field(min_length=1, description="the whole new text, numbers as slots")
    evidence_ids: list[str] = Field(default_factory=list, description="bullets only: the ids its numbers come from")

    @model_validator(mode="after")
    def _ids(self):
        self.evidence_ids = norm_ids(self.evidence_ids)
        bad = [e for e in self.evidence_ids if not re.match(EVIDENCE_ID, e)]
        if bad:
            raise ValueError(f"evidence ids must look like kpi.weekly / audit.week / insight.<id> / context.<name>: {bad}")
        return self


class DeckPatch(BaseModel):
    """A rewrite after the Validator (§5c, P6-6): replacements for the failing texts only; code merges them."""
    fixes: list[Fix] = Field(description="one replacement per failing text")


# --- Validator ------------------------------------------------------------------------------------------------------

class Problem(BaseModel):
    # V1 citation, V2 number, V3 draft label, V4 deck shape; Phase 6 (§5c): V5 evidence per slide, V6 direction,
    # V7 attribution, V8 the rendered PPTX; weekly-pack plan Phase D: V9 the claim check (W-R6)
    rule: Literal["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10"]   # V10: traffic-billing link plan
    slide: int | None = None
    bullet: int | None = Field(default=None, description="index of the bullet in DeckDraft.bullets")
    token: str | None = Field(default=None, description="the number token that failed, if any")
    message: str


class Verdict(BaseModel):
    passed: bool
    problems: list[Problem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self):
        if self.passed == bool(self.problems):
            raise ValueError("a verdict passes exactly when it has no problems")
        return self


# --- Approval (the interrupt's resume value) ------------------------------------------------------------------------

# Approver-additions plan (APPROVED 2026-11-06): an `edit` changes text, adds bullets or changes charts (no LLM call);
# a `revise` changes the Insight notes and / or steers the Insight agent, then the Writer drafts again (owner C1); one
# kind per decision (D1); caps D3. These classes are the approver's input, never an LLM schema: the Writer's
# `DeckDraft` is unchanged, so its prompt stays byte-identical (ADR-052 not triggered).

MAX_ADDITION_CHARS = 300
MAX_STEER_CHARS = 300
MAX_ANALYSIS_EDITS = 10
MAX_CHART_CHANGES = 3
MAX_NOTE_CHARS = 400


class Edit(BaseModel):
    bullet: int = Field(ge=0, description="index in DeckDraft.bullets")
    text: str = Field(min_length=1)


class Addition(BaseModel):
    """A new bullet the approver writes (owner B2): appended after the Writer's bullets of a free-text slide; its
    numbers are literals bound to that slide's evidence by the Validator (V2's human-edit path)."""
    slide: int = Field(ge=1, le=SLIDES)
    text: str = Field(min_length=1, max_length=MAX_ADDITION_CHARS)


class ChartChoice(BaseModel):
    """A variant of a pack chart from `deck/charts.py` (owner C2); None = keep that option's default."""
    chart: Literal[charts.PACK_CHARTS]  # pyright: ignore[reportInvalidTypeForm] (Literal built from the data tuple)
    series: list[Literal[tuple(charts.TREND_SERIES)]] | None = None  # pyright: ignore[reportInvalidTypeForm]
    weeks: Literal[charts.TREND_WEEKS] | None = None  # pyright: ignore[reportInvalidTypeForm]
    measure: Literal[tuple(charts.VARIANCE_MEASURES)] | None = None  # pyright: ignore[reportInvalidTypeForm]
    rows: Literal[charts.ROWS] | None = None  # pyright: ignore[reportInvalidTypeForm]

    @model_validator(mode="after")
    def _options(self):
        given = {k for k in ("series", "weeks", "measure", "rows") if getattr(self, k) is not None}
        extra = given - set(charts.OPTIONS[self.chart])
        if extra:
            raise ValueError(f"the {self.chart} chart has no option {sorted(extra)}")
        if not given:
            raise ValueError(f"a {self.chart} change names at least one of {list(charts.OPTIONS[self.chart])}")
        return self


# which operations each part of the notes allows (plan §2b): the five summary points and the code-chosen drivers keep
# their count, so only their wording changes
ANALYSIS_OPS = {"summary": ("replace",), "driver": ("replace",), "context": ("replace", "remove", "add"),
                "caveat": ("replace", "remove", "add")}


class AnalysisEdit(BaseModel):
    target: Literal["summary", "driver", "context", "caveat"]
    op: Literal["replace", "remove", "add"]
    index: int | None = Field(default=None, ge=0, description="replace / remove: the position in that list")
    text: str | None = Field(default=None, min_length=1, max_length=MAX_NOTE_CHARS,
                             description="replace / add; a driver's replace is its explanation")
    evidence_ids: list[str] = Field(default_factory=list,
                                    description="summary / context: ids already in the run's evidence")

    @model_validator(mode="after")
    def _shape(self):
        if self.op not in ANALYSIS_OPS[self.target]:
            raise ValueError(f"{self.target}: only {list(ANALYSIS_OPS[self.target])}")
        if (self.op in ("replace", "remove")) != (self.index is not None):
            raise ValueError("an index is given exactly for replace / remove")
        if (self.op != "remove") != (self.text is not None):
            raise ValueError("a text is given exactly for replace / add")
        if self.evidence_ids and self.target in ("driver", "caveat"):
            raise ValueError(f"a {self.target} carries no evidence ids (a driver keeps its own)")
        self.evidence_ids = norm_ids(self.evidence_ids)
        bad = [e for e in self.evidence_ids if not re.match(EVIDENCE_ID, e)]
        if bad:
            raise ValueError(f"evidence ids must look like kpi.weekly / audit.week / insight.<id> / context.<name>: {bad}")
        return self


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "edit", "revise", "reject"]
    approver_employee_id: int = Field(ge=1, description="checked in PostgreSQL: a Finance manager or the CEO")
    edits: list[Edit] = Field(default_factory=list)
    additions: list[Addition] = Field(default_factory=list)
    charts: list[ChartChoice] = Field(default_factory=list, max_length=MAX_CHART_CHANGES)
    analysis_edits: list[AnalysisEdit] = Field(default_factory=list, max_length=MAX_ANALYSIS_EDITS)
    steer: str | None = Field(default=None, min_length=1, max_length=MAX_STEER_CHARS)
    comment: str | None = None

    @model_validator(mode="after")
    def _kind(self):
        text = bool(self.edits or self.additions)
        analysis = bool(self.analysis_edits or self.steer)
        if self.decision == "edit" and not (text or self.charts):
            raise ValueError("an 'edit' carries edits, additions or chart changes")
        if self.decision == "edit" and analysis:
            raise ValueError("analysis edits and a steer belong to 'revise'")
        if self.decision == "revise" and not analysis:
            raise ValueError("a 'revise' carries analysis edits and / or a steer")
        if self.decision == "revise" and text:
            raise ValueError("a 'revise' re-drafts the deck, so text edits and additions go in a later 'edit' (D1)")
        if self.decision in ("approve", "reject") and (text or analysis or self.charts):
            raise ValueError(f"'{self.decision}' carries no changes")
        if len({c.chart for c in self.charts}) != len(self.charts):
            raise ValueError("one change per chart")
        return self


# --- Views (plan §2d, owner C3): a reader's chart, chosen from the catalogue -----------------------------------------

class ViewChoice(BaseModel):
    """What the views endpoint draws. Also the schema of its one structured call: the model sees the question and this
    catalogue only, never data (owner D5); `week` None → the API asks back."""
    kind: Literal[charts.VIEW_KINDS]  # pyright: ignore[reportInvalidTypeForm] (Literal built from the data tuple)
    week: int | None = Field(default=None, ge=1, le=52, description="ISO week of 2025; null when the question names none")
    series: list[Literal[tuple(charts.TREND_SERIES)]] | None = Field(  # pyright: ignore[reportInvalidTypeForm]
        default=None, description="trend only: 1-3 fields of one unit")
    # an int, not a Literal: Gemini's schema takes string enums only (Views_eval run 1); the catalogue checks it
    weeks: int | None = Field(default=None, description="trend only: the window, 4, 8, 13 or 26 weeks")
    measure: str | None = Field(default=None, description="category: billed_sdr / budget_variance_sdr / "
                                                          "budget_variance_pct / billed_wow_change_sdr; customers: "
                                                          "share_13w_pct / ar_sdr / overdue_sdr")
    rows: Literal[charts.ROWS] | None = Field(  # pyright: ignore[reportInvalidTypeForm]
        default=None, description="category only")
    compare_week: int | None = Field(default=None, ge=1, le=52, description="category / aging: a second week")

    @model_validator(mode="after")
    def _catalogue(self):
        bad = charts.view_problems(self.model_dump())
        if bad:
            raise ValueError("; ".join(bad))
        return self


Unit = Literal["SDR", "%", "days"]


class ViewSeries(BaseModel):
    name: str
    values: list[float | None]


class ViewSpec(BaseModel):
    """A drawn view: every value a field of a finance view (= Power BI = the pack); the caption is code's."""
    choice: ViewChoice
    categories: list[str]
    series: list[ViewSeries]
    unit: Unit
    caption: str
    sources: list[dict] = Field(default_factory=list, description="the tool results used: view + filter")


# --- Finance Q&A (Agents plan Phase 7, §5d P7-1: `graphs/finance_qa.py`) --------------------------------------------

class QaAnswer(BaseModel):
    """The answer to one finance question: numbers as slots (deck/slots.py), the evidence they come from."""
    status: Literal["answered", "not_in_data", "not_permitted"] = Field(description=(
        "answered = the tools gave the answer; not_in_data = the data or documents do not hold it; not_permitted = "
        "a tool refused this user's access"))
    answer: str = Field(min_length=1, max_length=1500, description=(
        "the answer in the question's language, two to four sentences; every PortPilot number written as a slot"))
    evidence_ids: list[str] = Field(default_factory=list, description="ids of the tool results the answer uses")

    @model_validator(mode="after")
    def _ids(self):
        self.evidence_ids = norm_ids(self.evidence_ids)
        bad = [e for e in self.evidence_ids if not re.match(EVIDENCE_ID, e)]
        if bad:
            raise ValueError(f"evidence ids look like insight.<id> (from the evidence list): {bad}")
        return self


class SupervisorAnswer(QaAnswer):
    """The answer of the supervisor over both products (Agents plan Phase 12, §6d P12-3): `partial` = the permitted
    parts answered and the refused part named (which part is refused is decided by code, never by the model)."""
    status: Literal["answered", "partial", "not_in_data", "not_permitted"] = Field(description=(
        "answered = the tools gave the whole answer; partial = the permitted parts answered and the part listed as "
        "not permitted named, without its figures; not_in_data = the data does not hold it; not_permitted = nothing "
        "asked is permitted to this user"))
    answer: str = Field(min_length=1, max_length=2000, description=(
        "the answer in the question's language, two to six sentences; every PortPilot number written as a slot"))


# --- Route advice (Agents plan Phase 10, §6b: `graphs/route_advice.py`) ---------------------------------------------

ROUTE_EVIDENCE_ID = r"^route\.[a-z_]+$"
ROUTES = ("suez", "cape")
ROUTE_STATUSES = ("ok", "no_suez_on_route", "suez_only", "not_permitted", "no_data", "output_invalid",
                  "validation_failed")


class RouteRequest(BaseModel):
    """One question: a vessel (one of ours, or a hypothetical one) and a voyage; the clock comes from the run context."""
    vessel_id: int | None = Field(default=None, ge=1)
    vessel_type: str | None = None
    condition: Literal["Laden", "Ballast"] | None = None
    scnt_tons: float | None = Field(default=None, gt=0)
    origin: str = Field(pattern=r"^[A-Z]{2}[A-Z2-9]{3}$")
    destination: str = Field(pattern=r"^[A-Z]{2}[A-Z2-9]{3}$")
    speed_kn: float | None = Field(default=None, ge=4, le=25)

    @model_validator(mode="after")
    def _vessel(self):
        hypothetical = [self.vessel_type, self.condition, self.scnt_tons]
        if self.vessel_id is None and any(v is None for v in hypothetical):
            raise ValueError("give vessel_id, or vessel_type + condition + scnt_tons")
        if self.vessel_id is not None and any(v is not None for v in hypothetical):
            raise ValueError("give vessel_id alone, or the hypothetical vessel, not both")
        if self.origin == self.destination:
            raise ValueError("origin and destination must differ")
        return self


class RouteReason(BaseModel):
    text: str = Field(min_length=1, max_length=400, description="one sentence; every number written as a slot")
    evidence_ids: list[str] = Field(default_factory=list, description="ids of the route.* results it uses")

    @model_validator(mode="after")
    def _ids(self):
        bad = [e for e in self.evidence_ids if not re.match(ROUTE_EVIDENCE_ID, e)]
        if bad:
            raise ValueError(f"evidence ids look like route.compare / route.difference / route.news: {bad}")
        return self


class RouteAdvice(BaseModel):
    """What the advisor writes (skill `route-cost-advice`): the choice, a headline and the reasons, numbers as slots;
    the comparison table, the assumptions and the sources are written by code."""
    recommendation: Literal[ROUTES] = Field(description="suez or cape")  # pyright: ignore[reportInvalidTypeForm] (Literal built from the data tuple)
    headline: str = Field(min_length=1, max_length=300, description="one sentence: the choice and its main reason")
    reasons: list[RouteReason] = Field(min_length=1, max_length=5, description="cost, time and risk reasons")
    risks: list[RouteReason] = Field(default_factory=list, max_length=4,
                                     description="external context only (route.traffic, route.news): no PortPilot "
                                                 "number; 'context unavailable' when a tool said so")


class RouteAdviceResult(BaseModel):
    """The answer the graph returns and keeps in its checkpoint (one thread per question, P10-3)."""
    status: Literal[ROUTE_STATUSES]  # pyright: ignore[reportInvalidTypeForm] (Literal built from the data tuple)
    request: dict
    as_of: str
    comparison: list[dict] = Field(default_factory=list, description="route.compare rows (+ the difference row)")
    recommendation: Literal[ROUTES] | None = None  # pyright: ignore[reportInvalidTypeForm] (Literal built from the data tuple)
    headline: str | None = None
    reasons: list[str] = Field(default_factory=list, description="rendered: slots filled by code")
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    problems: list[str] = Field(default_factory=list)


# --- Voyage watch (Agents plan Phase 11, §6c: `graphs/voyage_watch.py`) ---------------------------------------------

ALERT_ID = r"^\d+/(weather|suez_traffic|rta_late|jit)$"
WATCH_STATUSES = ("ok", "no_data", "not_permitted")
BRIEF_STATUSES = ("ok", "no_alerts", "output_invalid", "validation_failed")


class WatchRequest(BaseModel):
    """One watch run; the clock comes from the run context. `vessel_ids` = a subset (the checks); None = the fleet."""
    vessel_ids: list[int] | None = Field(default=None, min_length=1, max_length=500)


class WatchItem(BaseModel):
    text: str = Field(min_length=1, max_length=400, description="one sentence; every number written as a slot")
    # a Suez traffic drop is a fleet-wide event: one sentence may cite every vessel with the canal ahead (D-P11-1)
    alert_ids: list[str] = Field(min_length=1, max_length=60,
                                 description="the alerts this sentence is about, e.g. 36/weather, 112/suez_traffic; "
                                             "one Suez traffic sentence may list every suez_traffic alert")

    @model_validator(mode="after")
    def _ids(self):
        bad = [a for a in self.alert_ids if not re.match(ALERT_ID, a)]
        if bad:
            raise ValueError(f"alert ids look like <vessel_id>/weather, /suez_traffic, /rta_late or /jit: {bad}")
        return self


class WatchBrief(BaseModel):
    """What the brief writer returns (skill `voyage-watch-brief`): a headline and up to six items about the alerts,
    numbers as slots; the alert table, the ETAs, the assumptions and the sources are written by code."""
    headline: str = Field(min_length=1, max_length=300, description="one sentence: how many vessels are at risk and "
                                                                    "the most serious alert")
    items: list[WatchItem] = Field(min_length=1, max_length=6, description="every high alert first, then moderate")


class VoyageWatchResult(BaseModel):
    """What one watch run returns and saves (the thread's checkpoint + the run file, P11-5)."""
    status: Literal[WATCH_STATUSES]  # pyright: ignore[reportInvalidTypeForm] (Literal built from the data tuple)
    as_of: str
    fleet: dict = Field(default_factory=dict, description="watch.fleet: counts by status, alerts, weather points")
    etas: list[dict] = Field(default_factory=list, description="one row per vessel at sea / at anchor")
    alerts: list[dict] = Field(default_factory=list, description="watch.alerts rows, high first")
    brief_status: Literal[BRIEF_STATUSES] | None = None  # pyright: ignore[reportInvalidTypeForm] (Literal built from the data tuple)
    headline: str | None = None
    items: list[dict] = Field(default_factory=list, description="rendered: slots filled by code, with alert ids")
    assumptions: list[str] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    problems: list[str] = Field(default_factory=list)
    run_file: str | None = None


# --- Arrival advice (JIT arrival plan §3, D-J1: `graphs/arrival_advice.py`) ------------------------------------------

ARRIVAL_EVIDENCE_ID = r"^arrival\.[a-z_]+$"
ARRIVAL_OPTIONS = ("keep", "jit", "floor", "catch_up", "cape")
ARRIVAL_STATUSES = ("ok", "on_time", "late", "not_at_sea", "not_destination", "no_rta", "not_permitted", "no_data",
                    "output_invalid", "validation_failed")


class ArrivalRequest(BaseModel):
    """One question: one of our vessels at sea, optionally its port (must be the voyage's destination) and an RTA
    (else the RTA known at the clock from the port-call messages); the clock comes from the run context."""
    vessel_id: int = Field(ge=1)
    port: str | None = Field(default=None, pattern=r"^[A-Z]{2}[A-Z2-9]{3}$")
    rta_utc: datetime | None = None
    location: Literal["berth", "pilot_boarding_place"] = "berth"

    @model_validator(mode="after")
    def _utc(self):
        if self.rta_utc is not None and (self.rta_utc.tzinfo is None or self.rta_utc.utcoffset() is None):
            raise ValueError("rta_utc must carry its time zone (UTC, e.g. 2026-09-15T14:00Z)")
        return self


class ArrivalReason(BaseModel):
    text: str = Field(min_length=1, max_length=400, description="one sentence; every number written as a slot")
    evidence_ids: list[str] = Field(default_factory=list, description="ids of the arrival.* results it uses")

    @model_validator(mode="after")
    def _ids(self):
        bad = [e for e in self.evidence_ids if not re.match(ARRIVAL_EVIDENCE_ID, e)]
        if bad:
            raise ValueError(f"evidence ids look like arrival.options / arrival.summary / arrival.weather: {bad}")
        return self


class ArrivalAdvice(BaseModel):
    """What the advisor writes (skill `arrival-advice`): the option, a headline and the reasons, numbers as slots; the
    option table, the assumptions and the sources are written by code."""
    recommendation: Literal[ARRIVAL_OPTIONS] = Field(description="one of the computed options: keep, jit, floor, catch_up or cape")  # pyright: ignore[reportInvalidTypeForm] (Literal built from the data tuple)
    headline: str = Field(min_length=1, max_length=300, description="one sentence: the speed to sail and its main reason")
    reasons: list[ArrivalReason] = Field(min_length=1, max_length=5, description="time, fuel and risk reasons")
    risks: list[ArrivalReason] = Field(default_factory=list, max_length=4,
                                       description="weather on the next legs and Suez traffic only (arrival.weather, "
                                                   "arrival.traffic); 'context unavailable' when a tool said so")


class ArrivalAdviceResult(BaseModel):
    """The answer the graph returns and keeps in its checkpoint (one thread per question)."""
    status: Literal[ARRIVAL_STATUSES]  # pyright: ignore[reportInvalidTypeForm] (Literal built from the data tuple)
    request: dict
    as_of: str
    summary: dict = Field(default_factory=dict, description="arrival.summary: the RTA, the target, the situation")
    options: list[dict] = Field(default_factory=list, description="arrival.options rows")
    recommendation: Literal[ARRIVAL_OPTIONS] | None = None  # pyright: ignore[reportInvalidTypeForm] (Literal built from the data tuple)
    headline: str | None = None
    reasons: list[str] = Field(default_factory=list, description="rendered: slots filled by code")
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    problems: list[str] = Field(default_factory=list)
