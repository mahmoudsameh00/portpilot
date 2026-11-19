# Review of the owner-run application database audit

Source: `2026-11-12_stabilization_report.txt`, reviewed 2026-11-12. The report reaches `### END`, contains
sections 0–28 and no ERROR/FATAL/WARNING lines, and shows `default_transaction_read_only = on`.
The original report is preserved unchanged. The assistant did not connect to the database.

Observed results:

- PostgreSQL 16.9 / PostGIS 3.5.2. Public data: 837 ports, 19,990 connections, 500 vessels, 1,000 containers,
  100 employees, 1,000 invoices, 994 payments, 40 customers and 676 budget rows.
- Geometry/orphan/route consistency, email uniqueness, invoice amount/category/condition, MMSI and FK-index
  checks show no new inconsistencies. The three live duplicate-charge findings and five test findings match
  the audit's documented reviewed/planted cases; they are not newly introduced failures.
- Finance: 18 views, zero missing view/column comments, zero unauthorized BI writes or reads outside finance,
  and AR roll-forward difference 0.00. The planted budget miss and test-week deltas match the reviewed values.
- API/agent permissions match the restricted grants: no runtime password writes or audit deletion; no
  readonly/BI access to login hashes or agent state. Existing application users remain unchanged.
- Documents: 29 documents / 2,163 chunks; all registered as ingested. This checks PostgreSQL registry rows,
  not a fresh Qdrant inspection.
- Traffic: 371 days / 14,263 transits / no missing days. Scenario: 1,000 invoices / 994 payments, preserved
  amounts and payment delays, alpha 1.6. Three M17 views; live/test link weeks 0/0; scenario 29, starting week
  24; week-52 correlations 0.020 live / 0.497 scenario. All match the SQL's expected values. BI can read live
  M17 but not test/scenario. Zero missing finance view comments supports migration 028's intended coverage;
  the exact definitions/comment text still need the refreshed schema snapshot.

One open diagnostic: section 15 reports `tables_never_analyzed = 15`. Inspection of the audit SQL shows that
it only counts NULL `last_analyze` and `last_autoanalyze`; it does not inspect stored planner statistics.
The alias/comment have been corrected for future reports. A counter reset is a possible explanation, not an
established cause. `db/verify_planner_stats.sql` collects reset context, table estimates, column-statistics counts
and activity timestamps without running maintenance. No missing-statistics/performance claim is established yet.

Reference: PostgreSQL distinguishes [cumulative activity statistics](https://www.postgresql.org/docs/16/monitoring-stats.html)
from [ANALYZE's stored planner statistics](https://www.postgresql.org/docs/16/sql-analyze.html). An unclean restart
can reset the former; the diagnostic will inspect both. This audit does not replace model/Power BI/full API acceptance.

## Follow-up: planner statistics are present

Owner output `2026-11-12_planner_stats_report.txt` was reviewed on 2026-11-12. It reaches END without SQL errors
and confirms read-only mode, track_counts and autovacuum on, default_statistics_target 100. All 15 public project
tables have visible column statistics: 119 rows in total, matching their 119 statistics-enabled columns. Each
table's pg_class row estimate matches its exact row count in the earlier full audit (15/15, no differences).
All last_analyze/last_autoanalyze timestamps remain NULL; n_mod_since_analyze is 0. The server start is recorded
as 2026-11-12 06:07:18.221588+00, but database_counters_reset_at is NULL, so this report does not establish why
the activity timestamps are absent. A reset/restart cause must not be stated as confirmed.

The missing-planner-statistics concern is resolved for these tables. No ANALYZE/rebuild is recommended solely
because of the timestamp count. Statistics presence and matching row estimates do not prove distribution
freshness or query performance. No database maintenance was performed. Next: collect and review a fresh schema-only
snapshot through migrations 027/028 before replacing the repository's stale snapshot.
