# PortPilot branding and compatibility

The owner renamed the product to **PortPilot** on 2026-11-11. Current UI, API title, prompts, report headers,
download names, package metadata and Power BI project use that name. The logo is an original vector P/port mark
with a navigation arrow. Use `portpilot-logo.svg` for a wordmark, the shell `Brand.tsx` for the adaptive UI mark,
and `web/src/app/icon.svg` for the browser icon. Navy/blue on light backgrounds; white/light blue on navy.

`PORTPILOT_API_URL` and `PORTPILOT_WEB_ORIGIN` are the preferred web settings. Legacy `NILEGATE_*` settings still
work as fallback when the new keys are absent. Existing sessions keep their `ng_session` / `ng_csrf` cookie names.
The API's current problem-type namespace is `urn:portpilot:problem:*`.

The following names are retained as existing resource identities, not current branding:

- Qdrant collection `nilegate_docs`, MongoDB reader `nilegate_reader`, and existing employee email addresses.
- LangSmith project `nilegate-agents` and Sentry monitor `nilegate-weekly-pack`, preserving their history and alerts.
- Persisted agent metadata keys such as `nilegate_calls` / `nilegate_stop` and existing checkpoints/caches.
- Previously published reports, frozen evaluation questions/results, database migrations/audits, historical ADRs
  and archived documents. These are original evidence, not files to rewrite for branding.

No credentials, database records or remote service settings were changed. Renaming these resource identities
requires an owner-run migration, credential/configuration updates and a verified reconnect.

The Power BI project is now `powerbi/PortPilot_Finance.pbip`, with matching report and semantic-model folders.
Only branding and paths changed; model/data definitions remain intact. Existing open Desktop sessions should
be closed and the new project opened; runtime parity is still an owner check.

Scheduler registration scripts now create `PortPilot Weekly Finance Pack` and `PortPilot Voyage Watch` and refuse
to register while the corresponding legacy task remains enabled. To migrate, the owner first verifies the old
task is not running, disables it, then runs the corresponding registration script and checks its next run time.
Keep the disabled task until the new firing is verified. No scheduled task was modified during this rebrand.

The current upload format is `docs/templates/PortPilot_document_v1.md`: `PORTPILOT-DOC v1`, PP document codes
and PortPilot footers. The old marker, NG codes and NileGate footers also remain accepted under the same checks.
Keep the code when revising an existing document; issue PP codes for new documents. The old example and fixture
generator remain historical evidence. Do not overwrite approved/published artifacts merely to change branding.
