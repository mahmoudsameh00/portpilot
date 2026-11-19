-- 027_kpi_traffic_link.sql — written by hand (traffic-billing link plan Phase 3, docs/plans/Traffic_billing_link_plan.md §3c)
-- M17 (docs/finance_metrics.md): does NileGate's weekly invoice count move with the weekly Suez transits?
-- One view per dataset, the same body: finance (live), finance_test (evaluation copy), finance_scenario (the labelled
-- scenario of migration 026, planted α = 1.6).
-- Per report week w: Pearson r over weeks 1 … w (year to date) of the invoice count against the same week's transits
-- (lag 0) and the previous week's (lag 1); "link" when |r| ≥ 2 / √n for either lag; NULL in weeks 1–12 (n < 13).
-- Week numbers use floor(… / 7.0): integer division truncates toward zero and would put the lag week's days into
-- week 1 (D-TL-4). r and the threshold are rounded once, at the end; the link test uses the unrounded values.
-- A correlation is not a cause: "link" means "moves with", never "caused by" (plan §5).
BEGIN;

-- ---------------------------------------------------------------- finance (live)
CREATE VIEW finance.kpi_traffic_link AS
WITH t AS (
    SELECT floor((date - DATE '2024-12-30') / 7.0)::integer + 1 AS week, sum(n_total) AS transits
    FROM external.suez_transits_daily GROUP BY 1
), k AS (
    SELECT kw.report_week, kw.invoices_billed, t0.transits AS transits_week, t1.transits AS transits_prev_week
    FROM finance.kpi_weekly kw
    JOIN t t0 ON t0.week = kw.report_week
    JOIN t t1 ON t1.week = kw.report_week - 1
), r AS (
    SELECT k.*, count(*) OVER w AS n_weeks,
           corr(invoices_billed::float8, transits_week::float8) OVER w AS r0,
           corr(invoices_billed::float8, transits_prev_week::float8) OVER w AS r1
    FROM k
    WINDOW w AS (ORDER BY report_week ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
)
SELECT report_week,
       invoices_billed,
       transits_week::integer AS suez_transits_week,
       transits_prev_week::integer AS suez_transits_prev_week,
       n_weeks::integer AS n_weeks,
       CASE WHEN n_weeks >= 13 THEN round(r0::numeric, 3) END AS r_lag0,
       CASE WHEN n_weeks >= 13 THEN round(r1::numeric, 3) END AS r_lag1,
       CASE WHEN n_weeks >= 13 THEN round((2 / sqrt(n_weeks))::numeric, 3) END AS r_threshold,
       CASE WHEN n_weeks < 13 THEN NULL
            WHEN abs(r0) >= 2 / sqrt(n_weeks) OR abs(r1) >= 2 / sqrt(n_weeks) THEN 'link'
            ELSE 'no_link' END AS link,
       CASE WHEN n_weeks < 13 THEN NULL
            WHEN abs(r0) >= 2 / sqrt(n_weeks) AND abs(r0) >= coalesce(abs(r1), 0) THEN 0
            WHEN abs(r1) >= 2 / sqrt(n_weeks) THEN 1
            WHEN abs(r0) >= 2 / sqrt(n_weeks) THEN 0 END AS link_lag
FROM r;

-- ---------------------------------------------------------------- finance_test (evaluation copy)
CREATE VIEW finance_test.kpi_traffic_link AS
WITH t AS (
    SELECT floor((date - DATE '2024-12-30') / 7.0)::integer + 1 AS week, sum(n_total) AS transits
    FROM external.suez_transits_daily GROUP BY 1
), k AS (
    -- finance_test.kpi_weekly holds only the 4 test weeks (10, 23, 36, 49): the live weeks with those 4 counts
    -- swapped for the copy's (the migration 017 pattern), so the year-to-date window has all 52 weeks
    SELECT kw.report_week, coalesce(tw.invoices_billed, kw.invoices_billed) AS invoices_billed,
           t0.transits AS transits_week, t1.transits AS transits_prev_week
    FROM finance.kpi_weekly kw
    LEFT JOIN finance_test.kpi_weekly tw ON tw.report_week = kw.report_week
    JOIN t t0 ON t0.week = kw.report_week
    JOIN t t1 ON t1.week = kw.report_week - 1
), r AS (
    SELECT k.*, count(*) OVER w AS n_weeks,
           corr(invoices_billed::float8, transits_week::float8) OVER w AS r0,
           corr(invoices_billed::float8, transits_prev_week::float8) OVER w AS r1
    FROM k
    WINDOW w AS (ORDER BY report_week ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
)
SELECT report_week,
       invoices_billed,
       transits_week::integer AS suez_transits_week,
       transits_prev_week::integer AS suez_transits_prev_week,
       n_weeks::integer AS n_weeks,
       CASE WHEN n_weeks >= 13 THEN round(r0::numeric, 3) END AS r_lag0,
       CASE WHEN n_weeks >= 13 THEN round(r1::numeric, 3) END AS r_lag1,
       CASE WHEN n_weeks >= 13 THEN round((2 / sqrt(n_weeks))::numeric, 3) END AS r_threshold,
       CASE WHEN n_weeks < 13 THEN NULL
            WHEN abs(r0) >= 2 / sqrt(n_weeks) OR abs(r1) >= 2 / sqrt(n_weeks) THEN 'link'
            ELSE 'no_link' END AS link,
       CASE WHEN n_weeks < 13 THEN NULL
            WHEN abs(r0) >= 2 / sqrt(n_weeks) AND abs(r0) >= coalesce(abs(r1), 0) THEN 0
            WHEN abs(r1) >= 2 / sqrt(n_weeks) THEN 1
            WHEN abs(r0) >= 2 / sqrt(n_weeks) THEN 0 END AS link_lag
FROM r;

-- ---------------------------------------------------------------- finance_scenario (labelled scenario, α = 1.6)
CREATE VIEW finance_scenario.kpi_traffic_link AS
WITH t AS (
    SELECT floor((date - DATE '2024-12-30') / 7.0)::integer + 1 AS week, sum(n_total) AS transits
    FROM external.suez_transits_daily GROUP BY 1
), k AS (
    SELECT kw.report_week, kw.invoices_billed, t0.transits AS transits_week, t1.transits AS transits_prev_week
    FROM finance_scenario.kpi_weekly kw
    JOIN t t0 ON t0.week = kw.report_week
    JOIN t t1 ON t1.week = kw.report_week - 1
), r AS (
    SELECT k.*, count(*) OVER w AS n_weeks,
           corr(invoices_billed::float8, transits_week::float8) OVER w AS r0,
           corr(invoices_billed::float8, transits_prev_week::float8) OVER w AS r1
    FROM k
    WINDOW w AS (ORDER BY report_week ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
)
SELECT report_week,
       invoices_billed,
       transits_week::integer AS suez_transits_week,
       transits_prev_week::integer AS suez_transits_prev_week,
       n_weeks::integer AS n_weeks,
       CASE WHEN n_weeks >= 13 THEN round(r0::numeric, 3) END AS r_lag0,
       CASE WHEN n_weeks >= 13 THEN round(r1::numeric, 3) END AS r_lag1,
       CASE WHEN n_weeks >= 13 THEN round((2 / sqrt(n_weeks))::numeric, 3) END AS r_threshold,
       CASE WHEN n_weeks < 13 THEN NULL
            WHEN abs(r0) >= 2 / sqrt(n_weeks) OR abs(r1) >= 2 / sqrt(n_weeks) THEN 'link'
            ELSE 'no_link' END AS link,
       CASE WHEN n_weeks < 13 THEN NULL
            WHEN abs(r0) >= 2 / sqrt(n_weeks) AND abs(r0) >= coalesce(abs(r1), 0) THEN 0
            WHEN abs(r1) >= 2 / sqrt(n_weeks) THEN 1
            WHEN abs(r0) >= 2 / sqrt(n_weeks) THEN 0 END AS link_lag
FROM r;

-- ---------------------------------------------------------------- comments (the same for the three views)
COMMENT ON VIEW finance.kpi_traffic_link IS 'M17 (docs/finance_metrics.md): year-to-date Pearson r of the weekly invoice count against weekly Suez transits (IMF PortWatch), lag 0 and 1; "link" = moves with, never a cause. Live data (migration 027)';
COMMENT ON VIEW finance_test.kpi_traffic_link IS 'M17 on the evaluation copy: the live weeks with the 4 test weeks'' invoice counts from finance_test.kpi_weekly (the migration 017 pattern); otherwise the definition of finance.kpi_traffic_link (migration 027)';
COMMENT ON VIEW finance_scenario.kpi_traffic_link IS 'Scenario (planted: α = 1.6 × the real 2025 Suez traffic swing) — not NileGate''s billing. M17 on the scenario; same definition as finance.kpi_traffic_link (migration 027)';
DO $$
DECLARE s text;
BEGIN
  FOREACH s IN ARRAY ARRAY['finance', 'finance_test', 'finance_scenario'] LOOP
    EXECUTE format('COMMENT ON COLUMN %I.kpi_traffic_link.report_week IS %L', s, 'Report week 1-52 (ISO 2025)');
    EXECUTE format('COMMENT ON COLUMN %I.kpi_traffic_link.invoices_billed IS %L', s, 'Invoices issued in the week (kpi_weekly.invoices_billed of this schema)');
    EXECUTE format('COMMENT ON COLUMN %I.kpi_traffic_link.suez_transits_week IS %L', s, 'Suez Canal transits Monday-Sunday of the week (external.suez_transits_daily, n_total)');
    EXECUTE format('COMMENT ON COLUMN %I.kpi_traffic_link.suez_transits_prev_week IS %L', s, 'Suez Canal transits of the week before (lag 1; week 0 = 2024-12-23 ... 29)');
    EXECUTE format('COMMENT ON COLUMN %I.kpi_traffic_link.n_weeks IS %L', s, 'Weeks in the year-to-date window (= report_week)');
    EXECUTE format('COMMENT ON COLUMN %I.kpi_traffic_link.r_lag0 IS %L', s, 'Pearson r, weeks 1..w: invoice count vs the same week''s transits (3 decimals; NULL before week 13)');
    EXECUTE format('COMMENT ON COLUMN %I.kpi_traffic_link.r_lag1 IS %L', s, 'Pearson r, weeks 1..w: invoice count vs the previous week''s transits (3 decimals; NULL before week 13)');
    EXECUTE format('COMMENT ON COLUMN %I.kpi_traffic_link.r_threshold IS %L', s, '2 / sqrt(n_weeks): about the 5 % two-sided level for one test; two lags double the false rate (3 decimals)');
    EXECUTE format('COMMENT ON COLUMN %I.kpi_traffic_link.link IS %L', s, 'link when |r_lag0| or |r_lag1| >= r_threshold (unrounded), else no_link; NULL before week 13. Moves with, never caused by');
    EXECUTE format('COMMENT ON COLUMN %I.kpi_traffic_link.link_lag IS %L', s, 'The lag that passes (0 or 1; the larger |r| when both do); NULL when no_link or before week 13');
  END LOOP;
END $$;

GRANT SELECT ON finance.kpi_traffic_link TO ports_readonly;
GRANT SELECT ON finance_test.kpi_traffic_link TO ports_readonly;
GRANT SELECT ON finance_scenario.kpi_traffic_link TO ports_readonly;

COMMIT;
