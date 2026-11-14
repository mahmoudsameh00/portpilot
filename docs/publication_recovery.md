# Approved pack publication and recovery

New publications use `reports/2025-W<week>/publication.json` to select one complete immutable version under
`_publications/<id>/`. Each version contains `deck.pptx`, `deck_draft.json`, `approval.json` and `run.json`.
The API/download links resolve that version. Scripts should use the graph's `published.folder` or
`publications.current(week_folder)`; do not assume a new deck sits directly in the week folder.

When deploying this change, finish any old CLI/scheduler run and restart the API/web processes before the first
new publication, so every writer/reader uses the same version-directory protocol. No live service was restarted
during implementation.

The manifest records whether approved Power BI rows are `synced`, `pending`, or `not_required` (isolated/test
publications). Files are published first: a database outage never discards the approved deck. The API and web
show pending synchronization explicitly. Old packs without a manifest remain readable but their sync state is
`unknown`; the absence of a record does not establish that they match Power BI.

When a new pack shows pending synchronization, restore the database connection, then run this from the project
root using the actual week and an existing Finance manager or CEO employee ID:

```powershell
uv run python pipelines/scripts/agents/Weekly_pack.py reconcile --week <week> --as <employee-id>
```

This writes the same saved approved content to the existing approved-pack tables in a transaction. It neither
approves nor regenerates a pack and makes no model calls. Exit 0 means synced; exit 5 means the deck remains
saved but synchronization still needs attention. A corrupt version, busy week lock or legacy pack without a
manifest is refused. Inspect legacy records before any explicit migration; this command does not rewrite them.
Reload the pack/dashboard page to see the updated status, then compare Power BI's Approved Pack page with the
same week's web summary/charts. A `synced` record confirms the write, not that an already-open Power BI visual
has refreshed its display.

Scheduled product exits: 0 = completed/awaiting valid approval/idle; 1 = exception (including quota failures);
2 = database probe failure; 3 = invalid scheduled identity; 4 = stopped or incomplete product; 5 = saved output
with incomplete synchronization or missing watch brief. The durable JSONL records the operational outcome;
weekly-pack cron check-ins use the same exit code. Existing Windows task retry settings still apply.

No existing published files, database rows or scheduled tasks were migrated during implementation. Owner-run
database contention, recovery and Power BI parity checks remain part of stabilization acceptance.
