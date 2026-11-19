# Schema snapshot review — 2026-11-12

The owner exported `2026-11-12_schema_snapshot.sql` with PostgreSQL 16.9 pg_dump, schema-only,
no owner/privilege statements, excluding tiger, tiger_data and topology as documented in db/README.md.
The dump completion marker is present. The assistant inspected the files without connecting to PostgreSQL.

Comparison with the previous working snapshot:

- 576 added lines; no removed or rewritten lines.
- Three new views: `finance.kpi_traffic_link`, `finance_test.kpi_traffic_link`,
  `finance_scenario.kpi_traffic_link` (migration 027).
- All 56 added COMMENT statements exactly match the migration sources: 3 view and 30 column comments from
  migration 027, and all 23 approved-pack view-column comments from migration 028.
- The live/scenario view definitions differ only in their source KPI schema. The test view differs from live
  only by the intended test-week left join and COALESCE invoice-count substitution.
- Reviewed M17 logic matches migration 027: weekly PortWatch aggregation by floor, current/prior-week joins,
  year-to-date correlations, 13-week minimum, unrounded 2/sqrt(n) threshold, lag selection and three-decimal
  displayed correlations. The earlier full audit confirms the expected result values and access grants.
- No other schema-object changes were present. This export intentionally excludes grants; grant verification
  comes from `2026-11-12_stabilization_report.txt`, not this snapshot.

Promotion: previous `db/schema_snapshot.sql` preserved as `2026-11-12_schema_before_refresh.sql`; verified
owner export copied byte-for-byte to `db/schema_snapshot.sql`. Hashes checked before copying and after promotion:

| File | SHA-256 |
|---|---|
| Previous snapshot | `cf8b6313780ac6e16741a5731d1c1dde7e6118d938237319eae3812489414154` |
| Owner export / refreshed canonical snapshot | `73dc7f95e23c994632d473c6dee8b9693b09c9587d8beed7221b4bb649f25e92` |

Snapshot and read-only audit reconciliation through migrations 027/028 is complete. Independent full-data
finance/traffic checks, full API integration, model evaluation, Power BI acceptance and pushed CI remain separate
gates. No database modification, migration reapplication or application-data regeneration was performed.
