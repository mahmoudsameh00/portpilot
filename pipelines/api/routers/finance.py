"""The finance dashboard reads (Frontend plan D-FE-7, F0b): the Power BI pages drawn in the web from the same `finance`
views Power BI reads (ADR-048) and the pack's slots bind (ADR-051).

Thin wrappers over the agents' own tools — `finance_kpi` and `invoice_audit` — so the web and the agents share one RBAC
path (ADR-006: Finance, every manager, the CEO) and one column list; the API computes no KPI (ADR-047). No model, no
run: plain reads, each recorded in `api.audit_log`.
"""
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from pipelines.agents.tools import audit as audit_tool
from pipelines.agents.tools import context, db
from pipelines.agents.tools import finance as finance_tool
from pipelines.api import audit
from pipelines.api import finance_views as fv
from pipelines.api.auth import Principal, Signed
from pipelines.api.errors import ApiError, request_id

router = APIRouter(prefix="/finance", tags=["finance"])
Week = Annotated[int, Query(ge=1, le=52, description="ISO week of 2025 (as of its Sunday 23:59)")]


class SourceOut(BaseModel):
    kind: str
    name: str
    filter: str


class FinanceWeek(BaseModel):
    report_week: int
    iso_week_label: str
    week_end: str
    is_warmup: bool


class FinanceRows(BaseModel):
    """One dataset of `finance_kpi` for one week: its rows exactly as the view gives them."""
    dataset: Literal["weekly", "category", "customers", "overdue", "trend"]
    status: Literal["ok", "no_data"]
    note: str | None = None
    source: SourceOut | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)


class AuditRows(BaseModel):
    """`invoice_audit` for one week (or the year to date): the findings and the tool's own totals."""
    status: Literal["ok", "no_data"]
    note: str | None = None
    source: SourceOut | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    invoices_checked: int | None = None
    invoices_flagged: int | None = None
    amount_at_stake_sdr: float | None = None
    findings_by_check: dict[str, int] | None = None
    invoices_manual_review: int | None = None


class BreakdownRows(BaseModel):
    """`finance.kpi_weekly_breakdown` (M18) for one week and one dimension, largest member first."""
    dimension: fv.Dimension
    status: Literal["ok", "no_data"]
    note: str | None = None
    source: SourceOut | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)


def _gate(p: Principal, request: Request, what: str, week: int | None, action: str = "read",
          detail: dict | None = None) -> None:
    ok = context.permitted(p.user, context.FINANCE_VIEWS)
    audit.record(employee_id=p.employee_id, resource_type="finance", resource_id=what, action=action,
                 decision="allowed" if ok else "denied", request_id=request_id(request),
                 detail={**({"week": week} if week is not None else {}), **(detail or {})} or None)
    if not ok:
        raise ApiError(403, "the finance dashboard is Finance data (level 2)", slug="not_permitted")


def _out(res) -> dict:
    if res.status == "not_permitted":            # the tool's own refusal (the gate above makes it rare)
        raise ApiError(403, "not permitted for this user (ADR-006)", slug="not_permitted")
    return res.model_dump(mode="json", exclude={"tool"})


@router.get("/weeks", response_model=list[FinanceWeek])
def weeks(p: Signed, request: Request) -> list[dict]:
    """The report weeks the finance views hold, oldest first (the week picker)."""
    _gate(p, request, "weeks", None)
    rows = db.fetch("SELECT report_week, iso_week_label, week_end::text AS week_end, is_warmup "
                    "FROM finance.kpi_weekly ORDER BY report_week")
    return rows


@router.get("/invoice-audit", response_model=AuditRows)
def invoice_audit(p: Signed, request: Request, week: Week,
                  ytd: Annotated[bool, Query(description="weeks 1 … week (the year to date)")] = False) -> dict:
    _gate(p, request, "invoice-audit", week)
    return _out(audit_tool.invoice_audit(p.user, report_week=week, through_week=ytd))


@router.get("/breakdown", response_model=BreakdownRows)
def breakdown(p: Signed, request: Request, week: Week, dimension: fv.Dimension) -> dict:
    """The week's billing by one dimension (web dashboards plan, D-WD-4): count, SDR, tons, share, rank."""
    _gate(p, request, "breakdown", week, detail={"dimension": dimension})
    return {"dimension": dimension, **_out(fv.breakdown(p.user, week, dimension))}


@router.get("/export", response_class=Response,
            responses={200: {"content": {fv.XLSX: {"schema": {"type": "string", "format": "binary"}}},
                             "description": "the page's Excel workbook (a sheet per visual + About)"}})
def export(p: Signed, request: Request, week: Week, page: fv.Page) -> Response:
    """One dashboard page of one week as an Excel workbook (D-WD-2); allowed to whoever may read the dashboard
    (D-WD-3); every export is one `audit_log` row (action `export`)."""
    _gate(p, request, f"export:{page}", week, action="export")
    try:
        data, name, _ = fv.workbook(p.user, week, page, p.employee_id)
    except PermissionError:
        raise ApiError(403, "not permitted for this user (ADR-006)", slug="not_permitted") from None
    return Response(data, media_type=fv.XLSX, headers={
        "Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})


@router.get("/export/figure", response_class=Response,
            responses={200: {"content": {fv.XLSX: {"schema": {"type": "string", "format": "binary"}},
                                         "text/csv": {"schema": {"type": "string"}}},
                             "description": "one visual's or table's rows: a one-sheet workbook + About, or CSV"}})
def export_figure(
        p: Signed, request: Request, week: Week, figure: fv.Figure, format: fv.FileFormat = "xlsx",
        page: Annotated[fv.Page | None, Query(description="kpis: the page whose tiles are exported")] = None,
        dimension: Annotated[fv.Dimension | None, Query(description="breakdown: the dimension shown")] = None,
        compare: Annotated[int | None, Query(ge=1, le=52, description="breakdown: the compare week")] = None,
        ytd: Annotated[bool, Query(description="audit_*: the year to date")] = False,
        limit: Annotated[int | None, Query(ge=1, le=50, description="ranked lists: the rows the card shows")] = None,
) -> Response:
    """One figure of the dashboard (web dashboards plan amendment 1, D-WD-6): its rows exactly as the view gives them
    with the source view and filter; the same access rule as the dashboard (D-WD-3), one `audit_log` row each."""
    detail = {k: v for k, v in {"format": format, "page": page, "dimension": dimension, "compare": compare,
                                "ytd": ytd or None, "limit": limit}.items() if v is not None}
    _gate(p, request, f"export:{figure}", week, action="export", detail=detail)
    if figure == "breakdown" and dimension is None:
        raise ApiError(422, "a breakdown export needs its dimension", slug="invalid_request")
    try:
        data, name, media, _ = fv.figure_file(p.user, week, figure, format, p.employee_id, page=page,
                                              dimension=dimension, compare=compare, ytd=ytd, limit=limit)
    except PermissionError:
        raise ApiError(403, "not permitted for this user (ADR-006)", slug="not_permitted") from None
    return Response(data, media_type=media, headers={
        "Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})


@router.get("/{dataset}", response_model=FinanceRows)
def dataset(dataset: Literal["weekly", "category", "customers", "overdue", "trend"], p: Signed, request: Request,
            week: Week,
            limit: Annotated[int, Query(ge=1, le=50, description="rows of the ranked lists")] = 10) -> dict:
    _gate(p, request, dataset, week)
    out = _out(finance_tool.finance_kpi(p.user, report_week=week, dataset=dataset, limit=limit))
    return {"dataset": dataset, **out}
