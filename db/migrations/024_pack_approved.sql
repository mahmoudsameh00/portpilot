-- =====================================================================
-- 024 — The approved weekly pack in the database, for the Power BI "Approved pack" page
--       (approver-request plan §2c, docs/plans/Approver_request_plan.md, approved 2026-11-07; owner R1 = the web
--       dashboard + Power BI)
-- Why: when the Finance manager approves a pack (after his changes in words), the dashboard must show the same
-- approved summary and the same chart choices. Power BI reads PostgreSQL by DirectQuery through finance_bi (ADR-048)
-- and cannot read the pack's files; the web reads them through the API.
-- What:
--   * two tables in agent_state, written only by the pack's publisher on approve (login ports_agent, through 016's
--     default privileges for agent_writer): the approved choices of one report week and its summary lines;
--   * three read-only views in finance (013's default privileges give finance_bi and ports_readonly SELECT): the
--     summary, and the two pack charts as long rows — the existing finance views RESHAPED and FILTERED to the
--     approved choice. No KPI is computed here (ADR-047): every value is a column of finance.kpi_weekly or
--     finance.kpi_weekly_category, the same rows the deck's slots bind and the API's views draw. A view runs with its
--     owner's rights, so finance_bi needs nothing in agent_state.
-- Window and row rules = the deck's (`render.trend_window`, `render.variance_rows`): an N-week trend shows report
-- weeks max(1, w−N+1) … w; the variance rows are ordered by the measure ascending (NULL as 0) then the category, and
-- top5 / bottom5 keep the five largest / smallest.
-- Decisions: ADR-016 (migrations), ADR-047 (KPIs only in finance views), ADR-048 (Power BI), ADR-066 (the chart
-- catalogue: the CHECK lists below = pipelines/agents/deck/charts.py). Written by hand; never edited after applying.
-- =====================================================================
BEGIN;

-- the approved choices of a report week ---------------------------------
CREATE TABLE agent_state.pack_approved (
    report_week          integer PRIMARY KEY CHECK (report_week BETWEEN 1 AND 52),
    thread_id            text NOT NULL CHECK (thread_id LIKE 'weekly_pack:live:2025-W%'),
    approved_at          timestamptz NOT NULL,
    approver_employee_id integer NOT NULL,
    trend_series         text[] NOT NULL CHECK (cardinality(trend_series) BETWEEN 1 AND 3 AND trend_series <@
                             ARRAY['billed_sdr', 'budget_sdr', 'collected_sdr', 'ar_sdr', 'overdue_sdr', 'dso_days']),
    trend_weeks          integer NOT NULL CHECK (trend_weeks IN (4, 8, 13, 26)),
    variance_measure     text NOT NULL CHECK (variance_measure IN
                             ('budget_variance_sdr', 'budget_variance_pct', 'billed_wow_change_sdr')),
    variance_rows        text NOT NULL CHECK (variance_rows IN ('all', 'top5', 'bottom5')),
    degraded             boolean NOT NULL,
    published_at         timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE agent_state.pack_approved IS 'One row per report week with a published weekly pack (approver-request plan §2c): the chart choices as approved (defaults filled in) and who approved. Written only by the pack publisher on approve (a re-published week replaces its row); read by the finance.pack_* views.';
COMMENT ON COLUMN agent_state.pack_approved.trend_series IS 'The trend chart''s series (deck/charts.py TREND_SERIES keys), in drawing order';
COMMENT ON COLUMN agent_state.pack_approved.trend_weeks IS 'The trend chart''s window in weeks (4 / 8 / 13 / 26)';
COMMENT ON COLUMN agent_state.pack_approved.variance_measure IS 'The variance chart''s measure (a finance.kpi_weekly_category column)';
COMMENT ON COLUMN agent_state.pack_approved.variance_rows IS 'all / top5 / bottom5 categories by the measure';
COMMENT ON COLUMN agent_state.pack_approved.degraded IS 'true = code replaced or dropped some of the Writer''s texts (c4 fallback); read the deck before quoting it';

CREATE TABLE agent_state.pack_approved_summary (
    report_week integer NOT NULL REFERENCES agent_state.pack_approved (report_week) ON DELETE CASCADE,
    idx         integer NOT NULL CHECK (idx BETWEEN 0 AND 9),
    text        text NOT NULL CHECK (length(text) BETWEEN 1 AND 600),
    PRIMARY KEY (report_week, idx)
);
COMMENT ON TABLE agent_state.pack_approved_summary IS 'The approved executive summary of a report week (the deck''s slide 2, numbers filled in as the Validator passed them), one row per line.';

-- the views Power BI reads ----------------------------------------------
CREATE VIEW finance.pack_approved_summary AS
SELECT s.report_week, w.iso_week_label, s.idx + 1 AS line_no, s.text, p.approved_at, p.approver_employee_id,
       p.degraded
FROM agent_state.pack_approved_summary s
JOIN agent_state.pack_approved p USING (report_week)
JOIN finance.dim_week w USING (report_week);
COMMENT ON VIEW finance.pack_approved_summary IS 'The approved weekly pack''s executive summary (slide 2), one row per line, for the Power BI "Approved pack" page (migration 024).';

CREATE VIEW finance.pack_trend_long AS
SELECT p.report_week, t.report_week AS trend_week, t.iso_week_label AS trend_week_label,
       (t.report_week = p.report_week) AS is_report_week, s.ord AS series_order, s.series,
       CASE s.series WHEN 'billed_sdr' THEN 'Billed' WHEN 'budget_sdr' THEN 'Budget' WHEN 'collected_sdr' THEN 'Collected'
                     WHEN 'ar_sdr' THEN 'Receivables' WHEN 'overdue_sdr' THEN 'Overdue' WHEN 'dso_days' THEN 'DSO' END
           AS series_name,
       CASE WHEN s.series = 'dso_days' THEN 'days' ELSE 'SDR' END AS unit,
       CASE s.series WHEN 'billed_sdr' THEN t.billed_sdr WHEN 'budget_sdr' THEN t.budget_sdr
                     WHEN 'collected_sdr' THEN t.collected_sdr WHEN 'ar_sdr' THEN t.ar_sdr
                     WHEN 'overdue_sdr' THEN t.overdue_sdr WHEN 'dso_days' THEN t.dso_days END AS value
FROM agent_state.pack_approved p
CROSS JOIN LATERAL unnest(p.trend_series) WITH ORDINALITY AS s (series, ord)
JOIN finance.kpi_weekly t ON t.report_week BETWEEN greatest(1, p.report_week - p.trend_weeks + 1) AND p.report_week;
COMMENT ON VIEW finance.pack_trend_long IS 'The approved pack''s trend chart (slide 4) as long rows: the weeks of the approved window × the approved series, each value a finance.kpi_weekly column (migration 024; the deck''s render.trend_window).';

CREATE VIEW finance.pack_variance_long AS
WITH v AS (
    SELECT p.report_week, p.variance_measure AS measure, p.variance_rows, c.vessel_category,
           CASE p.variance_measure WHEN 'budget_variance_sdr' THEN c.budget_variance_sdr
                                   WHEN 'budget_variance_pct' THEN c.budget_variance_pct
                                   WHEN 'billed_wow_change_sdr' THEN c.billed_wow_change_sdr END AS value
    FROM agent_state.pack_approved p
    JOIN finance.kpi_weekly_category c USING (report_week)
), r AS (
    SELECT v.*, row_number() OVER (PARTITION BY report_week ORDER BY coalesce(value, 0), vessel_category) AS sort_order,
           count(*) OVER (PARTITION BY report_week) AS n
    FROM v
)
SELECT report_week, measure,
       CASE measure WHEN 'budget_variance_sdr' THEN 'Billed − budget' WHEN 'budget_variance_pct' THEN 'Billed vs budget %'
                    WHEN 'billed_wow_change_sdr' THEN 'Change on last week' END AS measure_name,
       CASE WHEN measure = 'budget_variance_pct' THEN '%' ELSE 'SDR' END AS unit,
       vessel_category, value, sort_order
FROM r
WHERE variance_rows = 'all' OR (variance_rows = 'top5' AND sort_order > n - 5)
   OR (variance_rows = 'bottom5' AND sort_order <= 5);
COMMENT ON VIEW finance.pack_variance_long IS 'The approved pack''s variance chart (slide 5) as rows: the categories of the report week by the approved measure, ascending (sort_order), all / top 5 / bottom 5 as approved; each value a finance.kpi_weekly_category column (migration 024; the deck''s render.variance_rows).';

COMMIT;
