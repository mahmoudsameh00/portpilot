-- 028_pack_views_column_comments.sql — written by hand (traffic-billing link plan, D-TL-5; owner: "اكتب وطبّق migration 028")
-- Comments only: the 23 columns of migration 024's three finance views had no COMMENT, so Finance_views_check.py
-- stopped at "views / columns without COMMENT: (0, 23)". No view, data or privilege changes.
BEGIN;

-- finance.pack_approved_summary (slide 2 of the approved pack, one row per line)
COMMENT ON COLUMN finance.pack_approved_summary.report_week IS 'Report week 1-52 (ISO 2025) of the approved pack';
COMMENT ON COLUMN finance.pack_approved_summary.iso_week_label IS 'The report week as an ISO label (finance.dim_week), e.g. 2025-W14';
COMMENT ON COLUMN finance.pack_approved_summary.line_no IS 'Position of the summary line on slide 2 (1 = first)';
COMMENT ON COLUMN finance.pack_approved_summary.text IS 'The approved summary line, numbers already rendered from their slots';
COMMENT ON COLUMN finance.pack_approved_summary.approved_at IS 'When the finance manager approved the pack (agent_state.pack_approved)';
COMMENT ON COLUMN finance.pack_approved_summary.approver_employee_id IS 'employees.employee_id of the approver';
COMMENT ON COLUMN finance.pack_approved_summary.degraded IS 'true = code replaced or dropped some of the Writer''s texts (c4 fallback); read the deck before quoting it';

-- finance.pack_trend_long (slide 4 of the approved pack, long rows)
COMMENT ON COLUMN finance.pack_trend_long.report_week IS 'Report week 1-52 (ISO 2025) of the approved pack';
COMMENT ON COLUMN finance.pack_trend_long.trend_week IS 'A week of the approved trend window (finance.kpi_weekly.report_week)';
COMMENT ON COLUMN finance.pack_trend_long.trend_week_label IS 'The trend week as an ISO label (finance.dim_week)';
COMMENT ON COLUMN finance.pack_trend_long.is_report_week IS 'true for the pack''s own report week (highlighted on the chart)';
COMMENT ON COLUMN finance.pack_trend_long.series_order IS 'Order of the series as approved (1 = first in the legend)';
COMMENT ON COLUMN finance.pack_trend_long.series IS 'The finance.kpi_weekly column the series shows (e.g. billed_sdr)';
COMMENT ON COLUMN finance.pack_trend_long.series_name IS 'Display name of the series';
COMMENT ON COLUMN finance.pack_trend_long.unit IS 'Unit of value: SDR, or days for dso_days';
COMMENT ON COLUMN finance.pack_trend_long.value IS 'The series value in trend_week, read from finance.kpi_weekly';

-- finance.pack_variance_long (slide 5 of the approved pack, one row per category)
COMMENT ON COLUMN finance.pack_variance_long.report_week IS 'Report week 1-52 (ISO 2025) of the approved pack';
COMMENT ON COLUMN finance.pack_variance_long.measure IS 'The finance.kpi_weekly_category column the chart shows, as approved (e.g. budget_variance_pct)';
COMMENT ON COLUMN finance.pack_variance_long.measure_name IS 'Display name of the measure';
COMMENT ON COLUMN finance.pack_variance_long.unit IS 'Unit of value: % for budget_variance_pct, else SDR';
COMMENT ON COLUMN finance.pack_variance_long.vessel_category IS 'Vessel category (toll category) of the row';
COMMENT ON COLUMN finance.pack_variance_long.value IS 'The measure for this category in the report week, read from finance.kpi_weekly_category';
COMMENT ON COLUMN finance.pack_variance_long.sort_order IS 'Ascending rank by value (then category) within the report week; the chart draws in this order';

COMMIT;
