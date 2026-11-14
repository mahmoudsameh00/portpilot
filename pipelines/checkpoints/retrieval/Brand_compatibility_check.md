# PortPilot compatibility — Final Checkpoint

The 2026-11-11 rebrand preserves accepted legacy uploads and their document/chunk identity. The parser accepts
both exact metadata markers and footer brands. Existing NG codes remain valid; newly issued documents can use
PP codes, with the same department/type/number restrictions. Revisions of an existing document keep its code.

The check reads the approved legacy DOCX example and makes only in-memory variants. It validates the old brand,
new brand with the old ID, and new PP ID through the real isolated document reader and full upload validator.
It checks that changing the displayed brand preserves existing chunk IDs, and rejects a mismatched department,
unknown marker and excessive access. No approved fixture or original example is overwritten.

Power BI's renamed PBIP resolves to its report and semantic model. All report/model JSON files parse. This is
source verification; opening Desktop and checking live data parity remains an owner-run integration check.

All 10 agent skills load within the established description and body limits. The longer name initially pushed
the supervisor description past its cap; shortening “one question” to “a question” preserved the meaning and
restored loading. Four phases; no network, database or artifact writes. Included in database-free CI.
