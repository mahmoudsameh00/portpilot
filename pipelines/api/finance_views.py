"""The web dashboard's own finance reads (web dashboards plan §2a–2b, owner decisions D-WD-2…4, 2026-11-15).

- `breakdown(user, week, dimension)` reads `finance.kpi_weekly_breakdown` (migration 029, M18): the week's billing by
  one dimension. Not a dataset of the agents' `finance_kpi` tool on purpose: that tool's argument list is part of the
  schema sent to the models, so a new value would change the cache key of every tools-role call (plan §2a).
- `workbook(user, week, page, employee_id)` builds the dashboard page's Excel export: one sheet per visual, rows exactly
  as the views give them (the agents' tools and this module's breakdown, so one RBAC path and one column list), and an
  "About" sheet (page, week, who, when, each sheet's source). No number is computed here (ADR-047).
- `figure_file(user, week, figure, fmt, …)` (amendment 1, D-WD-6) exports one visual or table: its rows exactly as
  the view gives them, as a one-sheet workbook + About, or as CSV whose every row names its source view and filter.
Both refuse a user outside the `finance_kpi` rule (ADR-006: Finance, every manager, the CEO) themselves, besides the
router's gate.
"""
import csv
import io
from datetime import datetime
from typing import Literal, cast, get_args
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from pipelines.agents.tools import audit as audit_tool
from pipelines.agents.tools import context, db
from pipelines.agents.tools import finance as finance_tool
from pipelines.agents.tools.schemas import Source, ToolResult

Dimension = Literal["vessel_category", "toll_band", "route", "priced_condition", "customer_segment",
                    "customer_country", "credit_rating"]
DIMENSIONS: tuple[str, ...] = get_args(Dimension)
DIMENSION_LABEL = {"vessel_category": "Vessel category", "toll_band": "Toll band (top band reached)",
                   "route": "Route", "priced_condition": "Laden / ballast", "customer_segment": "Customer segment",
                   "customer_country": "Customer country", "credit_rating": "Credit rating"}
# Excel sheet names: at most 31 characters, none of : \ / ? * [ ]
SHEET_NAME = {"vessel_category": "By vessel category", "toll_band": "By toll band", "route": "By route",
              "priced_condition": "Laden vs ballast", "customer_segment": "By customer segment",
              "customer_country": "By customer country", "credit_rating": "By credit rating"}
Page = Literal["overview", "revenue", "receivables", "customers", "exceptions", "executive"]
PAGES: tuple[str, ...] = get_args(Page)
BREAKDOWN_VIEW = "finance.kpi_weekly_breakdown"
BREAKDOWN_COLS = ("report_week", "dimension", "member", "invoices_billed", "billed_sdr", "scnt_tons", "share_pct",
                  "rank_in_week")
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CAIRO = ZoneInfo("Africa/Cairo")


def breakdown(user, week: int, dimension: str) -> ToolResult:
    if dimension not in DIMENSIONS:
        raise ValueError(f"unknown dimension {dimension!r}")
    if not context.permitted(user, context.FINANCE_VIEWS):
        return context.denied("finance_breakdown")
    rows = db.fetch(f"SELECT {', '.join(BREAKDOWN_COLS)} FROM {BREAKDOWN_VIEW} "
                    "WHERE report_week = %s AND dimension = %s ORDER BY rank_in_week", (week, dimension))
    flt = f"report_week = {week} AND dimension = '{dimension}' ORDER BY rank_in_week"
    if not rows:
        return ToolResult(tool="finance_breakdown", status="no_data", note=f"{BREAKDOWN_VIEW}: no rows for {flt}")
    return ToolResult(tool="finance_breakdown", status="ok", rows=rows,
                      source=Source(kind="view", name=BREAKDOWN_VIEW, filter=flt))


# --- the Excel export ------------------------------------------------------------------------------------------------

AGING = (("aging_current_sdr", "Current"), ("aging_1_30_sdr", "1-30 days"), ("aging_31_60_sdr", "31-60 days"),
         ("aging_61_90_sdr", "61-90 days"), ("aging_90_plus_sdr", "90+ days"))
WEEKLY_FIELDS = {
    "overview": ("billed_sdr", "budget_sdr", "budget_variance_sdr", "budget_variance_pct", "budget_variance_13w_pct",
                 "collected_sdr", "ar_sdr", "overdue_sdr", "dso_days", "invoices_billed", "top10_share_13w_pct",
                 "billed_wow_pct", "collected_wow_pct", "ar_wow_pct", "overdue_wow_pct", "dso_wow_days"),
    "revenue": ("invoices_billed", "billed_sdr", "budget_sdr", "budget_variance_sdr", "budget_variance_pct"),
    "receivables": ("ar_sdr", "collected_sdr", "overdue_sdr", "dso_days", "dso_best_days", "dso_delinquency_days",
                    "due_week_sdr", "due_week_collected_sdr", "due_week_collected_pct", "overdue_new_sdr",
                    "overdue_paid_sdr") + tuple(f for f, _ in AGING),
    "customers": ("billed_13w_sdr", "top10_share_13w_pct", "ontime_13w_pct"),
    "executive": ("billed_sdr", "billed_13w_sdr", "budget_13w_sdr", "budget_variance_13w_pct", "overdue_sdr",
                  "dso_days", "ontime_13w_pct"),
}


class _Sheet:
    def __init__(self, title: str, res: ToolResult, columns: tuple[str, ...] | None = None, vertical: bool = False):
        self.title, self.res, self.columns, self.vertical = title[:31], res, columns, vertical


def _ok(res: ToolResult) -> ToolResult:
    if res.status == "not_permitted":
        raise PermissionError("not permitted (ADR-006)")
    return res


def _sheets(user, week: int, page: str) -> list[_Sheet]:
    def kpi(dataset: str, limit: int = 10) -> ToolResult:
        return _ok(finance_tool.finance_kpi(user, report_week=week, dataset=dataset, limit=limit))

    def bd(dim: str) -> ToolResult:
        return _ok(breakdown(user, week, dim))

    weekly = kpi("weekly")
    out = [_Sheet("Weekly KPIs", weekly, ("report_week", "iso_week_label", *WEEKLY_FIELDS.get(page, ())), True)] \
        if page in WEEKLY_FIELDS else []
    if page == "overview":
        out.append(_Sheet("Trend 13 weeks", kpi("trend")))
    elif page == "revenue":
        out.append(_Sheet("Billed vs budget by category", kpi("category")))
        out += [_Sheet(SHEET_NAME[d], bd(d)) for d in ("toll_band", "route", "priced_condition", "customer_segment",
                                                        "customer_country", "credit_rating")]
        out.append(_Sheet("Trend 13 weeks", kpi("trend")))
    elif page == "receivables":
        out.append(_Sheet("Trend 13 weeks", kpi("trend")))
        out.append(_Sheet("Overdue invoices", kpi("overdue", 50)))
    elif page == "customers":
        out.append(_Sheet("Customers 13 weeks", kpi("customers", 50)))
    elif page == "exceptions":
        out += list(_audit(user, week, ytd=False))
    elif page == "executive":
        out.append(_Sheet("Trend 13 weeks", kpi("trend")))
    return out


def _fmt(col: str) -> str | None:
    if col.endswith("_sdr"):
        return "#,##0.00"
    if col.endswith("_pct"):
        return "0.00"
    if col.endswith("_days"):
        return "0.0"
    return None


def _autosize(ws) -> None:
    for i, col in enumerate(ws.iter_cols(min_row=1, max_row=min(ws.max_row, 200)), start=1):
        width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[get_column_letter(i)].width = min(max(width + 2, 10), 60)


HEAD = Font(bold=True, color="FFFFFF")
FILL = PatternFill("solid", fgColor="1F4E79")


def _write(ws, sheet: _Sheet) -> int:
    res = sheet.res
    rows = res.rows or []
    if res.status != "ok" or not rows:
        ws.append([res.note or "No rows for this week."])
        return 0
    cols = [c for c in (sheet.columns or tuple(rows[0])) if c in rows[0]]
    if sheet.vertical:                               # one row (the week's KPIs): one line per field
        ws.append(["field", "value"])
        for c in cols:
            ws.append([c, rows[0][c]])
            f = _fmt(c)
            if f and isinstance(rows[0][c], int | float):
                ws.cell(ws.max_row, 2).number_format = f
    else:
        ws.append(cols)
        for r in rows:
            ws.append([r.get(c) for c in cols])
        for j, c in enumerate(cols, start=1):
            if (f := _fmt(c)) is not None:
                for i in range(2, ws.max_row + 1):
                    ws.cell(i, j).number_format = f
        ws.auto_filter.ref = ws.dimensions
    for cell in ws[1]:
        cell.font, cell.fill = HEAD, FILL
    ws.freeze_panes = "A2"
    _autosize(ws)
    return len(rows)


def _week_label(week: int) -> str:
    return next((r["iso_week_label"] for r in db.fetch(
        "SELECT iso_week_label FROM finance.kpi_weekly WHERE report_week = %s", (week,))), f"2025-W{week:02d}")


def workbook(user, week: int, page: str, employee_id: int | None) -> tuple[bytes, str, dict]:
    """(xlsx bytes, file name, summary for the audit row). PermissionError when the user may not read the views."""
    if page not in PAGES:
        raise ValueError(f"unknown page {page!r}")
    if not context.permitted(user, context.FINANCE_VIEWS):
        raise PermissionError("not permitted (ADR-006)")
    sheets = _sheets(user, week, page)
    label = _week_label(week)
    data, counts = _xlsx((("Page", page.capitalize()), ("Week", label)), sheets, employee_id)
    return data, f"PortPilot_dashboard_{page}_{label}.xlsx", {"week": week, "page": page, "sheets": counts}


def _xlsx(head: tuple[tuple[str, object], ...], sheets: list[_Sheet], employee_id: int | None) -> tuple[bytes, dict]:
    """The workbook: an About sheet (`head`, who, when, money, definitions, each sheet's source) + one per sheet."""
    wb = Workbook()
    about = wb.active
    assert about is not None
    about.title = "About"
    now = datetime.now(CAIRO)
    about.append(["PortPilot finance dashboard — export"])
    about["A1"].font = Font(bold=True, size=13)
    for k, v in (*head, ("Exported by employee", employee_id),
                 ("Exported at (Cairo)", now.strftime("%Y-%m-%d %H:%M")),
                 ("Money", "SDR (Special Drawing Rights), as stored"),
                 ("Definitions", "docs/finance_metrics.md (one definition per KPI; computed only in the finance views)")):
        about.append([k, v])
    about.append([])
    about.append(["Sheet", "Rows", "Source view", "Filter"])
    for c in about[about.max_row]:
        c.font, c.fill = HEAD, FILL
    counts = {}
    for s in sheets:
        n = _write(wb.create_sheet(s.title), s)
        counts[s.title] = n
        about.append([s.title, n, s.res.source.name if s.res.source else "—",
                      s.res.source.filter if s.res.source else (s.res.note or "")])
    for row in about.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=False)
    _autosize(about)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), counts


# --- one figure (amendment 1, D-WD-6, owner 2026-11-15): the numbers of one visual or table ----------------------------

Figure = Literal["kpis", "trend", "category", "overdue", "customers", "breakdown", "audit_summary", "audit_findings"]
FIGURES: tuple[str, ...] = get_args(Figure)
FileFormat = Literal["xlsx", "csv"]
CSV = "text/csv; charset=utf-8"
FIGURE_SHEET = {"kpis": "Weekly KPIs", "trend": "Trend 13 weeks", "category": "Billed vs budget by category",
                "overdue": "Overdue invoices", "customers": "Customers 13 weeks", "audit_summary": "Audit summary",
                "audit_findings": "Audit findings"}


def _audit(user, week: int, ytd: bool) -> tuple[_Sheet, _Sheet]:
    a = cast(audit_tool.AuditResult, _ok(audit_tool.invoice_audit(user, report_week=week, through_week=ytd)))
    totals = {"report_week": week, "year_to_date": ytd, "invoices_checked": a.invoices_checked,
              "invoices_flagged": a.invoices_flagged, "amount_at_stake_sdr": a.amount_at_stake_sdr,
              "invoices_manual_review": a.invoices_manual_review,
              **{f"findings_{k}": v for k, v in (a.findings_by_check or {}).items()}}   # the tool's own totals
    src = a.source or Source(kind="view", name="finance.invoice_audit", filter=f"report_week = {week}")
    return (_Sheet("Audit summary", ToolResult(tool="invoice_audit", status="ok", rows=[totals], source=src),
                   vertical=True), _Sheet("Audit findings", a))


def _figure(user, week: int, figure: str, page: str | None, dimension: str | None, compare: int | None,
            ytd: bool, limit: int | None) -> _Sheet:
    if figure == "kpis":
        res = _ok(finance_tool.finance_kpi(user, report_week=week, dataset="weekly"))
        cols = ("report_week", "iso_week_label", *WEEKLY_FIELDS[page]) if page in WEEKLY_FIELDS else None
        return _Sheet(FIGURE_SHEET[figure], res, cols, vertical=True)
    if figure in ("trend", "category", "overdue", "customers"):
        res = _ok(finance_tool.finance_kpi(user, report_week=week, dataset=figure, limit=limit or 10))
        return _Sheet(FIGURE_SHEET[figure], res)
    if figure in ("audit_summary", "audit_findings"):
        return _audit(user, week, ytd)[0 if figure == "audit_summary" else 1]
    if figure != "breakdown" or dimension not in DIMENSIONS:
        raise ValueError("a breakdown needs a dimension" if figure == "breakdown" else f"unknown figure {figure!r}")
    now = _ok(breakdown(user, week, dimension))
    if compare is None or compare == week:
        return _Sheet(SHEET_NAME[dimension], now)
    then = _ok(breakdown(user, compare, dimension))            # the compare week's rows, under the shown week's
    rows = [*(now.rows or []), *(then.rows or [])]
    flt = f"report_week IN ({week}, {compare}) AND dimension = '{dimension}' ORDER BY report_week, rank_in_week"
    res = ToolResult(tool="finance_breakdown", status="ok" if rows else "no_data", rows=rows,
                     note=None if rows else f"{BREAKDOWN_VIEW}: no rows for {flt}",
                     source=Source(kind="view", name=BREAKDOWN_VIEW, filter=flt))
    return _Sheet(SHEET_NAME[dimension], res)


def _csv(sheet: _Sheet) -> bytes:
    """The sheet's rows as CSV (UTF-8 with a BOM so Excel reads it), each row carrying its source view and filter."""
    res = sheet.res
    src = (res.source.name, res.source.filter) if res.source else ("", res.note or "")
    buf = io.StringIO()
    w = csv.writer(buf)
    rows = res.rows or []
    if res.status != "ok" or not rows:
        w.writerow(["note", "source_view", "source_filter"])
        w.writerow([res.note or "No rows for this week.", *src])
    else:
        cols = [c for c in (sheet.columns or tuple(rows[0])) if c in rows[0]]
        if sheet.vertical:
            w.writerow(["field", "value", "source_view", "source_filter"])
            w.writerows([c, rows[0][c], *src] for c in cols)
        else:
            w.writerow([*cols, "source_view", "source_filter"])
            w.writerows([*(r.get(c) for c in cols), *src] for r in rows)
    return buf.getvalue().encode("utf-8-sig")


def figure_file(user, week: int, figure: str, fmt: str, employee_id: int | None, *, page: str | None = None,
                dimension: str | None = None, compare: int | None = None, ytd: bool = False,
                limit: int | None = None) -> tuple[bytes, str, str, dict]:
    """(bytes, file name, media type, summary for the audit row) of one figure. PermissionError / ValueError."""
    if figure not in FIGURES or fmt not in ("xlsx", "csv"):
        raise ValueError(f"unknown figure {figure!r} or format {fmt!r}")
    if not context.permitted(user, context.FINANCE_VIEWS):
        raise PermissionError("not permitted (ADR-006)")
    sheet = _figure(user, week, figure, page, dimension, compare, ytd, limit)
    label = _week_label(week)
    stem = "_".join(x for x in ("PortPilot", figure, dimension if figure == "breakdown" else None,
                                page if figure == "kpis" else None, label,
                                f"vs-W{compare:02d}" if figure == "breakdown" and compare and compare != week
                                else None, "ytd" if ytd and figure.startswith("audit") else None) if x)
    summary = {"week": week, "figure": figure, "format": fmt, "rows": len(sheet.res.rows or []),
               **({"page": page} if page else {}), **({"dimension": dimension} if dimension else {}),
               **({"compare": compare} if compare else {}), **({"ytd": True} if ytd else {})}
    if fmt == "csv":
        return _csv(sheet), f"{stem}.csv", CSV, summary
    head: tuple[tuple[str, object], ...] = (("Figure", sheet.title), ("Week", label))
    if figure == "breakdown":
        head += (("Break down by", DIMENSION_LABEL[cast(str, dimension)]),)
        if compare and compare != week:
            head += (("Compare week", _week_label(compare)),)
    if ytd and figure.startswith("audit"):
        head += (("Period", "Year to date"),)
    data, _ = _xlsx(head, [sheet], employee_id)
    return data, f"{stem}.xlsx", XLSX, summary
