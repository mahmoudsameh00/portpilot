-- 029_kpi_weekly_breakdown.sql — written by hand (web dashboards plan Phase 1, docs/plans/Web_dashboards_and_reports_plan.md §2a)
-- M18 (docs/finance_metrics.md): the week's billing broken down by one dimension at a time, in long format, so the
-- web dashboard's "Break down by" choice reads one view (owner decision D-WD-4, 2026-11-15). The same plain sums as
-- the Power BI measures `Revenue SDR` = SUM(Invoices[amount_sdr]), `Invoice Count` = COUNTROWS(Invoices),
-- `SCNT Tons` = SUM(Invoices[scnt_tons]) over the star of migration 013 (ADR-047: the number is written once, in SQL).
-- A week belongs to an invoice by its invoice_date inside dim_week's Monday-Sunday (as kpi_weekly / kpi_weekly_category).
-- Members with no invoice in the week are absent (a breakdown lists what was billed); for every week and dimension the
-- members' billed_sdr sum to kpi_weekly.billed_sdr (checked by Finance_views_check.py, Phase 8).
-- Live schema only: the evaluation copies (finance_test, finance_scenario) are read by the agents, which do not use it.
BEGIN;

CREATE VIEW finance.kpi_weekly_breakdown AS
WITH inv AS (
    SELECT w.report_week, f.invoice_id, f.amount_sdr, f.scnt_tons,
           f.vessel_category, f.priced_condition,
           tb.band_label AS toll_band,
           v.route,
           c.segment AS customer_segment, c.country AS customer_country, c.credit_rating
    FROM finance.dim_week w
    JOIN finance.fact_invoice f ON f.invoice_date BETWEEN w.week_start AND w.week_end
    LEFT JOIN finance.dim_toll_band tb ON tb.toll_rate_band_id = f.toll_rate_band_id
    LEFT JOIN finance.dim_vessel v ON v.vessel_id = f.vessel_id
    LEFT JOIN finance.dim_customer c ON c.customer_id = f.customer_id
), long AS (
    SELECT report_week, invoice_id, amount_sdr, scnt_tons, d.dimension, COALESCE(d.member, '(none)') AS member
    FROM inv
    CROSS JOIN LATERAL (VALUES
        ('vessel_category', vessel_category),
        ('toll_band', toll_band),
        ('route', route),
        ('priced_condition', priced_condition),
        ('customer_segment', customer_segment),
        ('customer_country', customer_country),
        ('credit_rating', credit_rating)
    ) AS d(dimension, member)
), agg AS (
    SELECT report_week, dimension, member,
           count(invoice_id) AS invoices_billed,
           sum(amount_sdr) AS billed_sdr,
           sum(scnt_tons) AS scnt_tons
    FROM long
    GROUP BY report_week, dimension, member
)
SELECT report_week,
       dimension,
       member,
       invoices_billed,
       round(billed_sdr, 2) AS billed_sdr,
       scnt_tons,
       round(100 * billed_sdr / NULLIF(sum(billed_sdr) OVER (PARTITION BY report_week, dimension), 0), 2) AS share_pct,
       rank() OVER (PARTITION BY report_week, dimension ORDER BY billed_sdr DESC, member) AS rank_in_week
FROM agg;

COMMENT ON VIEW finance.kpi_weekly_breakdown IS 'M18: the week''s billing by one dimension at a time (long format); members sum to kpi_weekly per week and dimension';
COMMENT ON COLUMN finance.kpi_weekly_breakdown.report_week IS 'Report week 1-52 (ISO 2025)';
COMMENT ON COLUMN finance.kpi_weekly_breakdown.dimension IS 'vessel_category | toll_band | route | priced_condition | customer_segment | customer_country | credit_rating';
COMMENT ON COLUMN finance.kpi_weekly_breakdown.member IS 'The dimension''s value (toll band = the top band reached, band_label; route = origin-destination UN/LOCODE; (none) when the invoice has no value)';
COMMENT ON COLUMN finance.kpi_weekly_breakdown.invoices_billed IS 'Invoices dated in the week with this member';
COMMENT ON COLUMN finance.kpi_weekly_breakdown.billed_sdr IS 'Sum of their amount_sdr (2 decimals)';
COMMENT ON COLUMN finance.kpi_weekly_breakdown.scnt_tons IS 'Sum of their Suez Canal net tons';
COMMENT ON COLUMN finance.kpi_weekly_breakdown.share_pct IS 'billed_sdr / the week''s billed_sdr over all members of this dimension, percent (2 decimals)';
COMMENT ON COLUMN finance.kpi_weekly_breakdown.rank_in_week IS '1 = the largest billed_sdr of the week for this dimension (ties by member name)';

GRANT SELECT ON finance.kpi_weekly_breakdown TO ports_readonly;
GRANT SELECT ON finance.kpi_weekly_breakdown TO finance_bi;

COMMIT;
