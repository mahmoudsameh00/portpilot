# Final Checkpoint — API integration

Implemented 2026-11-12 for approved stabilization R10. Owner-run database validation passed 5/5 the same day,
exit 0 in 64s. Evidence: `dev/db_audit/postgres/2026-11-12_api_integration_report.txt`, confirmed against the saved run log.

0. An explicit DSN guard rejects seven missing, production, remote or option-injected targets before connecting.
1. A fresh disposable database receives migration-derived API tables/grants and seven deterministic profiles.
   Each signs in through the actual API; stored tokens must equal their SHA-256 hashes.
2. Conversations test owner access, other-user hiding and CEO read-only access. The runtime cannot change password
   hashes or delete the append-only audit log.
3. A deterministic worker tests owned run status and SSE replay with real authentication, then token revocation.
4. Independent PostgreSQL connections must contend on the shared thread lock and release it afterwards. An invalid
   replacement summary must roll back the real approved-pack transaction; a valid retry must replace it.

The earlier full API suite borrowed employees without logins, failing once the sole CEO had a normal account.
Both paths now use reserved fixture IDs. The old suite is guarded to an isolated full-data clone; the new CI suite
needs only PostgreSQL and no `.env`, business data or providers. No automatic database/container deletion.

The owner ran `dev/tests/run_api_integration.ps1`: all phases passed, including actual fixture bootstrap, runtime
grants, locks and transaction rollback/retry. No changes to Data/processed or db/migrations were reported.
The test container was retained. Full-data application/Power BI acceptance and pushed CI remain unverified.
