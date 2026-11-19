# Publication consistency and recovery — Final Checkpoint

Stabilization R9 preserves the approved deck while making database synchronization durable and visible.
`pipelines/agents/publications.py` writes all four files into a temporary directory, flushes and reloads their
hashes, moves the complete directory to an immutable version, and atomically replaces `publication.json` for
the week. Readers resolve that manifest once and verify the selected files. An interrupted staging/pointer
write leaves the prior complete pack readable. A completed version left unreferenced by an interruption is
retained; no automatic deletion of published history is introduced.

The manifest starts with `db_sync=pending` for real live publications. The existing `store_approved` transaction
writes the saved summary/choices/approver. Success atomically updates the manifest to `synced`; failure retains
the deck, a pending state, attempt metadata and a warning. Only the exception class is recorded, never arbitrary
connection/error text. A crash after DB commit but before updating the manifest can safely replay the same
approved payload. Publishing the same inputs again reuses the selected version. A per-week filesystem lock
serializes publication and reconciliation across API/CLI processes sharing this local reports directory.

`Weekly_pack.py reconcile --week <week> --as <employee>` checks the existing Finance-manager/CEO rule and
retries the current saved publication, without an approval action, graph invocation, model call or re-render.
It does not silently migrate a legacy publication lacking a verified manifest. Legacy folders remain readable
and are labelled `unknown`; earlier versions superseded by another thread are labelled `superseded`.

API pack/detail and finance/dashboard responses expose `publication_sync`; downloads resolve the saved version
with the usual week-based filename. The web warns on pending, unknown and superseded states. Scheduler reports
read the selected version, and scheduled publication with pending sync is operationally degraded (exit 5).
The original four file names remain inside each version; owner-run checks now use the published resolved path.

Five validation phases cover complete commit and idempotent repair; failures at staging, pointer replacement
and after DB commit; mutual exclusion, corruption refusal, legacy reads and API status; the real publisher node
with stubbed renderer/DB and expiry; and the reconciliation CLI's authorization/no-model contract. All pass with
zero data/migration artifacts changed. This proves the local protocol, not live PostgreSQL/Power BI parity or
hardware power-loss behavior. Rendering/V8 are stubbed in these fault tests; existing owner-backed deck checks
still apply. Two browser scenarios run on desktop/mobile, including axe and no horizontal overflow.
