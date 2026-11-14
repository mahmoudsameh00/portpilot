"""The chart catalogue: which variants of a chart the approver (weekly pack) and a reader (the views API) may ask for.

Approver-additions plan §2c / §2d (APPROVED 2026-11-06, owner C2 / C3). One catalogue serves the pack's approval, the
views endpoint and, later, the web UI (`GET /api/v1/charts/catalogue`). Every variant is a choice among **fields the
finance views already return** (`tools/finance.py` DATASETS): code draws them with the tool's exact values and V8
reads them back, so a person or a model chooses *what* is shown, never a number (ADR-051).

Pure data + rules: no import from the graph, the renderer or the tools (`graphs/models.py` reads it for its
`Literal`s). A choice is a plain dict, e.g. {"chart": "trend", "series": ["billed_sdr", "collected_sdr"], "weeks": 8}.

Window rule (plan Phase A finding): the data hold 2025 only, so an N-week window needs report week ≥ N; the default
13-week trend keeps today's behaviour (weeks 1–w while the year has fewer weeks).
"""

# --- the weekly pack: charts the approver may change ----------------------------------------------------------------

# trend (slide 4): fields of `finance_kpi(trend)` → (series name as drawn, unit). The default's names are the ones the
# renderer draws today ("Billed", "Budget"), so a deck without changes stays byte-identical.
TREND_SERIES = {"billed_sdr": ("Billed", "SDR"), "budget_sdr": ("Budget", "SDR"),
                "collected_sdr": ("Collected", "SDR"), "ar_sdr": ("Receivables", "SDR"),
                "overdue_sdr": ("Overdue", "SDR"), "dso_days": ("DSO", "days")}
TREND_WEEKS = (4, 8, 13, 26)
MAX_SERIES = 3

# variance (slide 5): fields of `finance_kpi(category)` → (series name, unit)
VARIANCE_MEASURES = {"budget_variance_sdr": ("Billed − budget", "SDR"),
                     "budget_variance_pct": ("Billed vs budget %", "%"),
                     "billed_wow_change_sdr": ("Change on last week", "SDR")}
ROWS = ("all", "top5", "bottom5")          # top / bottom 5 by the measure; "all" = every category (today)

PACK_CHARTS = ("trend", "variance")
FIXED_CHARTS = ("aging", "overdue_flow", "suez")   # no variant of real value (plan Phase A)
DEFAULTS = {"trend": {"chart": "trend", "series": ["billed_sdr", "budget_sdr"], "weeks": 13},
            "variance": {"chart": "variance", "measure": "budget_variance_sdr", "rows": "all"}}
OPTIONS = {"trend": ("series", "weeks"), "variance": ("measure", "rows")}

# --- the views API: what a reader may ask for (plan §2d) ------------------------------------------------------------

VIEW_KINDS = ("trend", "category", "aging", "customers")
CATEGORY_MEASURES = {"billed_sdr": ("Billed", "SDR"), **VARIANCE_MEASURES}
AGING_BUCKETS = (("aging_current_sdr", "Current"), ("aging_1_30_sdr", "1–30 days"),
                 ("aging_31_60_sdr", "31–60 days"), ("aging_61_90_sdr", "61–90 days"),
                 ("aging_90_plus_sdr", "90+ days"))      # = render.AGING (Deck_check guards the equality)
CUSTOMER_MEASURES = {"share_13w_pct": ("Share of billed, 13 weeks %", "%"), "ar_sdr": ("Receivables", "SDR"),
                     "overdue_sdr": ("Overdue", "SDR")}
VIEW_OPTIONS = {"trend": ("series", "weeks"), "category": ("measure", "rows", "compare_week"),
                "aging": ("compare_week",), "customers": ("measure",)}

FIRST_WEEK, LAST_WEEK = 1, 52


def _unit_problems(series: list[str]) -> list[str]:
    out = []
    if not 1 <= len(series) <= MAX_SERIES:
        out.append(f"a trend shows 1 to {MAX_SERIES} series, got {len(series)}")
    unknown = [s for s in series if s not in TREND_SERIES]
    if unknown:
        out.append(f"unknown series {unknown}; allowed: {', '.join(TREND_SERIES)}")
    elif len({TREND_SERIES[s][1] for s in series}) > 1:
        out.append("one unit per chart: SDR series and DSO days cannot share an axis")
    if len(set(series)) != len(series):
        out.append("a series is named twice")
    return out


def _window_problems(weeks, week: int) -> list[str]:
    if weeks not in TREND_WEEKS:
        return [f"weeks must be one of {TREND_WEEKS}, got {weeks}"]
    if weeks != DEFAULTS["trend"]["weeks"] and week < weeks:
        return [f"a {weeks}-week window needs report week {weeks} or later (the data start in 2025-W01); "
                f"week {week} has {week}"]
    return []


def problems(choice: dict, week: int) -> list[str]:
    """Why a pack chart choice cannot be drawn for report `week` ([] = it can). Shape errors and catalogue rules in one
    list, worded for the approver."""
    chart = choice.get("chart")
    if chart in FIXED_CHARTS:
        return [f"the {chart} chart has no variants"]
    if chart not in PACK_CHARTS:
        return [f"unknown chart {chart!r}; the pack's charts with variants: {', '.join(PACK_CHARTS)}"]
    extra = sorted(k for k, v in choice.items() if k != "chart" and v is not None and k not in OPTIONS[chart])
    out = [f"the {chart} chart has no option {extra}"] if extra else []
    full = {**DEFAULTS[chart], **{k: v for k, v in choice.items() if v is not None}}
    if chart == "trend":
        out += _unit_problems(list(full["series"])) + _window_problems(full["weeks"], week)
    else:
        if full["measure"] not in VARIANCE_MEASURES:
            out.append(f"unknown measure {full['measure']!r}; allowed: {', '.join(VARIANCE_MEASURES)}")
        if full["rows"] not in ROWS:
            out.append(f"rows must be one of {ROWS}, got {full['rows']!r}")
        if full["measure"] == "billed_wow_change_sdr" and week == FIRST_WEEK:
            out.append("week 1 has no previous week: no week-on-week change to draw")
    return out


def resolve(choice: dict) -> dict:
    """The full choice: the chart's defaults overlaid with the options given (None = keep the default)."""
    chart = choice["chart"]
    return {**DEFAULTS[chart], **{k: v for k, v in choice.items() if v is not None}}


def is_default(choice: dict) -> bool:
    return resolve(choice) == DEFAULTS[choice["chart"]]


def needs_previous_trend(choice: dict) -> bool:
    """A trend window longer than the 13 weeks `finance_kpi(trend, week)` returns: code also fetches
    `finance_kpi(trend, week − 13)` (evidence `kpi.trend_prev`)."""
    return choice.get("chart") == "trend" and resolve(choice)["weeks"] > 13


def view_problems(choice: dict) -> list[str]:
    """Why a views-API choice cannot be fetched ([] = it can). `week` None is not a problem here: the caller asks
    back (owner D5)."""
    kind, week = choice.get("kind"), choice.get("week")
    if kind not in VIEW_KINDS:
        return [f"unknown view {kind!r}; allowed: {', '.join(VIEW_KINDS)}"]
    extra = sorted(k for k, v in choice.items() if k not in ("kind", "week") and v is not None
                   and k not in VIEW_OPTIONS[kind])
    out = [f"the {kind} view has no option {extra}"] if extra else []
    for w in (week, choice.get("compare_week")):
        if w is not None and not FIRST_WEEK <= w <= LAST_WEEK:
            out.append(f"weeks of 2025 are {FIRST_WEEK}–{LAST_WEEK}, got {w}")
    if week is not None and choice.get("compare_week") == week:
        out.append("compare_week is the same week")
    if kind == "trend":
        out += _unit_problems(list(choice.get("series") or DEFAULTS["trend"]["series"]))
        weeks = choice.get("weeks") or DEFAULTS["trend"]["weeks"]
        if week is not None:
            out += _window_problems(weeks, week)
        elif weeks not in TREND_WEEKS:
            out.append(f"weeks must be one of {TREND_WEEKS}, got {weeks}")
    elif kind == "category":
        if (choice.get("measure") or "billed_sdr") not in CATEGORY_MEASURES:
            out.append(f"unknown measure; allowed: {', '.join(CATEGORY_MEASURES)}")
        if (choice.get("rows") or "all") not in ROWS:
            out.append(f"rows must be one of {ROWS}")
    elif kind == "customers" and (choice.get("measure") or "share_13w_pct") not in CUSTOMER_MEASURES:
        out.append(f"unknown measure; allowed: {', '.join(CUSTOMER_MEASURES)}")
    return out


def catalogue() -> dict:
    """The catalogue as plain data (the future `GET /api/v1/charts/catalogue`)."""
    return {"pack": {"charts": list(PACK_CHARTS), "fixed": list(FIXED_CHARTS), "defaults": DEFAULTS,
                     "trend": {"series": {k: {"name": n, "unit": u} for k, (n, u) in TREND_SERIES.items()},
                               "weeks": list(TREND_WEEKS), "max_series": MAX_SERIES},
                     "variance": {"measure": {k: {"name": n, "unit": u} for k, (n, u) in VARIANCE_MEASURES.items()},
                                  "rows": list(ROWS)}},
            "views": {"kinds": list(VIEW_KINDS), "options": {k: list(v) for k, v in VIEW_OPTIONS.items()},
                      "category": {k: {"name": n, "unit": u} for k, (n, u) in CATEGORY_MEASURES.items()},
                      "aging": [{"field": f, "name": n} for f, n in AGING_BUCKETS],
                      "customers": {k: {"name": n, "unit": u} for k, (n, u) in CUSTOMER_MEASURES.items()}}}
