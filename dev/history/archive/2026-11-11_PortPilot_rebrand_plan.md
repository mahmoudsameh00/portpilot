# PortPilot rebrand

Status: **IMPLEMENTED (2026-11-11)** — owner: “rename the whole project to PortPilot and adjust the logo on the new name”.
This is an additional scope alongside the approved engineering stabilization plan, not a replacement for it.


## Implementation record

- Current branding changed across the web, API, agent prompts, deck/report labels, package metadata, Power BI
  project paths and current documentation. `uv lock --offline` with the existing cache changed only the root
  project identity for this task; dependency pins remain unchanged. API snapshot/client artifacts regenerated.
- `Brand.tsx`, app SVG icon and `docs/brand/portpilot-logo.svg` provide the P/navigation mark. Desktop login,
  mobile home and desktop answer screenshots were inspected. Navy/blue/white tokens retained; responsive
  layout, EN/AR text and accessibility verified. Screenshots/logs are in `Notebooks/_scratch/portpilot-*` while
  the enclosing stabilization task remains active.
- Compatibility: legacy BFF env aliases and cookies retained. No live resource/account/credential changes.
  Scheduler registration refuses an enabled legacy task. Uploads accept old/new markers and brands, preserve
  NG identities and permit PP codes for new documents. The historical fixture generator/example were preserved.
  Original data, approved reports, frozen evaluations, migrations and historical ADR text were not rebranded.
- Validation: production browser suite **100 passed / 50 intentional skips**; all six frontend static suites
  pass. Python ruff/pyright 0; OpenAPI 34 paths and approval cases match. Upload/Power BI/skill compatibility **4/4**,
  72 JSON files parse and 10 skills load; scheduler scripts parse without execution. Lifecycle 3/3, approval safety 4/4,
  shared traffic claims 4/4, and monitoring 5 offline phases pass. No DB/model calls or data/migration writes.
- Issues found and resolved during validation: old error-page Logo import blocked the first build; upload
  footer matching initially needed legacy compatibility; one JSX line needed formatting; the longer name
  exceeded one skill-description cap, fixed by shortening its wording without changing meaning. Offline uv resolution
  needed access to the existing user cache. All final checks above passed after correction.
- Limits: old external database/monitoring identities are deliberately retained (ADR-068). Scheduler migration,
  Power BI runtime parity, real-model acceptance and pushed CI remain owner-run operational checks. No deployment
  or commit was performed. Continue the approved stabilization plan with R8/R9/R10 and remaining R7 work.

## Approved scope

Implementation:
1. Rename active product branding across the web UI, API, agent prompts, generated decks, operational messages,
   Power BI project and current documentation. Use PortPilot / portpilot / PORTPILOT consistently.
2. Replace the web gate mark with an original scalable P/navigation mark; supply a matching browser icon and
   reusable SVG. Keep the accepted blue/white palette, typeface and responsive layout.
3. Preserve original data, published reports, frozen evaluations, migrations, audits and historical decisions.
   Existing database identities, Qdrant collection, monitoring destinations and scheduled tasks need compatible
   handling, not silent resource creation. Document retained operational identifiers and migration steps.
4. Regenerate API client artifacts; run backend static/contract checks and relevant deterministic tests, frontend
   static checks, browser tests and screenshot review. Record every limitation and handoff in this plan.

No data reload, credential changes, live pack approval, deployment or Git commit is implied by the rebrand.

## Progress / deviations

- 2026-11-11: scope recorded from the explicit owner instruction. Existing logo is inline SVG in the shell and
  login; it can be edited as vector code. No raster image generation or new dependency is needed.
