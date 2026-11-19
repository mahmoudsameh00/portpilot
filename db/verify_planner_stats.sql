-- Read-only follow-up to the 2026-11-12 audit's 15 missing ANALYZE activity timestamps.
-- Does not run ANALYZE, reset counters or change table contents/settings permanently.
-- Column-statistics counts/row estimates are diagnostic evidence, not a freshness or performance guarantee.
\set ON_ERROR_STOP on
SET default_transaction_read_only = on;
\pset pager off
\pset null '<NULL>'

\echo '### 0. SERVER AND COUNTER CONTEXT'
SHOW default_transaction_read_only;
SHOW track_counts;
SHOW autovacuum;
SHOW default_statistics_target;
SELECT current_database() AS database,
       pg_postmaster_start_time() AS server_started_at,
       stats_reset AS database_counters_reset_at
FROM pg_stat_database
WHERE datname = current_database();

\echo '### 1. PUBLIC PROJECT TABLE ESTIMATES, COLUMN STATISTICS AND ACTIVITY TIMESTAMPS'
-- pg_stats is the readable view of ANALYZE's pg_statistic data; no histogram or sample values are exposed here.
-- A row count of -1 means pg_class has no table-size estimate. Compare estimates with the saved full audit.
-- Empty tables or columns/types excluded from analysis can legitimately have no column-statistics rows.
SELECT c.relname AS table_name,
       c.reltuples::bigint AS estimated_rows,
       c.relpages AS estimated_pages,
       (SELECT count(*) FROM pg_attribute a WHERE a.attrelid = c.oid AND a.attnum > 0
          AND NOT a.attisdropped AND a.attstattarget <> 0) AS columns_with_statistics_enabled,
       (SELECT count(*) FROM pg_stats p WHERE p.schemaname = n.nspname AND p.tablename = c.relname
          AND NOT p.inherited) AS visible_column_statistics,
       s.last_analyze,
       s.last_autoanalyze,
       s.n_mod_since_analyze,
       c.reloptions AS table_options
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname <> 'spatial_ref_sys'
ORDER BY c.relname;

\echo '### END'
