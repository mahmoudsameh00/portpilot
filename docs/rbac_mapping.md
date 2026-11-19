# RBAC mapping

Decision record: ADR-006 in `docs/decisions.md`. Status: **enforced** by `search_documents` inside Qdrant (2026-10-08, ADR-038) and by every Stage 1 agent tool before its query (2026-10-18, ADR-049: `pipelines/agents/tools/context.py`, RBAC matrix in `dev/checks/agents/Tools_check.py`); the API is not built yet.

## 1. Access rule

Every protected resource (a table, a document or a chunk) has two attributes:

- `sensitivity_level` ∈ {1, 2, 3}
- an owner `department` (must be a row in the `departments` table)

Every employee has a role (`roles.allowed_sensitivity_level`: employee = 1, manager = 2, ceo = 3) and a department.

```text
allowed(user, resource) =
       resource.sensitivity_level <= user.role.allowed_sensitivity_level      -- role ceiling
   OR (resource.department_id = user.department_id                           -- department grant
       AND resource.sensitivity_level <= 2)                                  -- level 3 stays role-only (CEO)
```

- Level 1: everyone.
- Level 2: managers and CEO, plus **any employee of the owner department** (e.g. Finance employees can read `invoices`).
- Level 3: CEO only. The department grant never unlocks level 3.
- Authorization is applied **inside** retrieval (a Qdrant payload filter or a SQL predicate), never after results are fetched.

Qdrant filter (conceptual): `sensitivity_level <= role_level OR (department == user_department AND sensitivity_level <= 2)`.

## 2. Structured tables (PostgreSQL)

| Table | Level | Owner department | Note |
|---|---:|---|---|
| `ports` | 1 | Operations | geographic reference |
| `port_connections` | 1 | Operations | aggregated flow statistics |
| `toll_rate_bands` | 1 | Finance | published tariff |
| `departments` | 1 | HR | organisational structure |
| `vessel_performance` | 1 | Operations | fuel and speed parameters per vessel category and size band, from a public study (migration 020, ADR-055) |
| `bunker_prices` | 1 | Operations | the dated public VLSFO price + USD-per-SDR rate set by the owner: a market price, not company finance (migration 020) |
| `port_call_messages` | 1 | Operations | the Requested Time of Arrival a port or agent sends a vessel (one row per message; synthetic now, real later; migration 030, JIT arrival plan D-J1) |
| `external.suez_transits_daily` | 1 | Operations | IMF PortWatch daily Suez Canal transits 2024-12-23 … 2025-12-28: public data, the same source as the `suez_transits` tool; read by the finance link view (migration 025, traffic-billing link plan) |
| `vessels` | 1 | Operations | daily operational data |
| `containers` | 1 | Operations | operational shipment data |
| `documents` | 1 | IT | RAG document registry |
| `roles` | 2 | IT | defines the permission system |
| `employees` | 2 | HR | contains PII (names, emails). HR employees get access through their department |
| `invoices` | 2 | Finance | financial data. Finance employees get access through their department |
| `customers` | 2 | Finance | commercial terms and credit rating of the billed companies (migration 012, Agents plan §4a R8) |
| `payments` | 2 | Finance | payments received per invoice (migration 012) |
| `budget_weekly` | 2 | Finance | weekly budget 2025 per vessel category (migration 012) |
| `finance_test.*` | 2 | Finance | evaluation copy with planted errors (migration 012); the answer key is outside the database |
| `finance.*` (views) | 2 | Finance | star + weekly KPI views of the Weekly Finance Pack (migration 013, Agents plan Phase 2); read as one unit by the finance tools and Power BI (login in group role `finance_bi`, SELECT on `finance` only). The dimension views over level-1 tables (`dim_date`, `dim_week`, `dim_vessel`, `dim_toll_band`) take the schema's level |
| `vessels.customer_id` | 1 | Operations | an id only (the vessels table stays level 1); the customer's details are level 2 |
| `finance.invoice_audit` / `finance_test.invoice_audit` (views, migration 015) | 2 | Finance | invoice audit findings (ADR-049); covered by the `finance.*` / `finance_test.*` rows; only the first is readable by `finance_bi` |
| `finance_test.kpi_weekly` / `finance_test.kpi_weekly_category` (views, migration 017) | 2 | Finance | twin KPI views of the evaluation copy (Agents plan Phase 7); covered by the `finance_test.*` row; not readable by `finance_bi` |
| `finance_scenario.*` (migration 026) | 2 | Finance | a labelled scenario (planted α = 1.6): the 2025 invoices re-dated to follow Suez traffic, payments with their delays kept, and twins of 8 finance views; for the traffic-billing link measure and its check; not readable by `finance_bi`; never shown as PortPilot's billing |
| `agent_state.*` (LangGraph checkpoints, migration 016) | 2 | Finance | the tool results of each pack run at rest (KPI rows, audit findings, drafts); no employee reads it directly: only the runtime login `ports_agent` (group role `agent_writer`, DML on this schema only) and the owner; `ports_readonly` and `finance_bi` get nothing (ADR-050). The pack itself runs as a Finance manager and the tools check RBAC on every call |
| `agent_state.llm_daily_usage` / `llm_minute_usage` (migration 023) | 1 | IT | shared LLM request / token counters (FastAPI plan C1 / C2): counts per model and day / minute, no content; written by `ports_agent` (llm.py) |
| `api.logins` / `api.tokens` (migration 023) | 3 | IT | password hashes (scrypt) and token hashes; no employee reads them: the runtime login `ports_api` (group role `api_writer`) reads a hash but never writes one; logins are created by the owner (`Api_admin.py`); `ports_readonly` and `finance_bi` get nothing |
| `api.conversations` / `api.conversation_turns` (migration 023) | as the answers' data (≤ 2) | the asker | conversation memory (§6a of the FastAPI plan): questions, masked answers (no numbers), entity frames; the owner of the conversation and the CEO only, through the API |
| `api.audit_log` (migration 023; ADR-014 redesign) | 3 | IT | security audit trail (who did / was refused what), append-only for `api_writer`; CEO only (and the owner) |

## 3. Semi-structured (MongoDB, implemented 2026-09-27)

| Collection | Level | Owner department |
|---|---:|---|
| `ais_positions` (time-series; real + synthetic fixes) | 1 | Operations |
| `ais_vessels` (static / voyage data per MMSI) | 1 | Operations |
| `edi_messages` | 1 | Operations (synthetic IFTMIN carries no amounts; can move to 2 later if commercial values must be restricted) |
| `voyages_synthetic.parquet` (the generator's voyage file, read by `voyage_status`) | 1 | Operations (the same data as the synthetic tracks; its `arrival_ts` is never returned before arrival, ADR-055) |

The agent tools read MongoDB as the read-only user `MONGO_RO_USER` (role `read`, 2026-10-27); the loader keeps the app user.

Every document carries `sensitivity_level` and `department` (as the chunks do), so the rule in §1 can be applied as a query predicate. Names replace the earlier `ais_events` (ADR-029). `edi_messages.keys.invoice_number` is a reference to a level-2 / Finance invoice, not its content (no amounts, D14), so the collection stays level 1; reading the invoice itself still needs level 2 or the Finance department. Implemented 2026-09-27: every document of the three collections carries level 1 / Operations (validated by the loader's schema audit).

## 4. Documents (RAG corpus)

External, publicly published sources are level 1. Their owner department is the PortPilot department that would use them.

| Document | Level | Owner department |
|---|---:|---|
| `LPI.pdf`, `LPI_Methodology.pdf` (World Bank) | 1 | Operations |
| `MSC-MEPC_3-Circ_4-Rev_1.pdf` (IMO) | 1 | Operations |
| USCG ROI reports ×23 | 1 | Operations |
| `FBL_template.pdf` (FIATA) | 1 | Operations |
| `Transit_Dues_Rates.pdf`, Notes section only (Suez Canal Authority) | 1 | Finance |
| `HbR_Annual_report_2025_highlights.pdf`: strategy, ESG, narrative | 1 | Operations |
| HbR: the Port Authority's own financial results and position — balance sheet and income statement (p.82), the 3.2.2 paragraphs on revenue, operating expenses, EBITDA / net result and gross investments, and the gross-investments chart (p.13) | **3** | Finance |

HbR is deliberately treated as "our internal report" so the corpus contains one document with sections at different levels. Sensitivity is stored per chunk. Implemented 2026-09-26 (ADR-021): every unit that mentions money or finance was reviewed; 37 units / 5 chunks are level 3, all others level 1, and no chunk mixes levels.

## 4a. Agent tools and external sources (ADR-049, 2026-10-18)

| Tool | Reads | Level | Owner department |
|---|---|---:|---|
| `finance_kpi`, `invoice_audit` | `finance.*` (live) / `finance_test.*` (evaluation runs only, chosen by the run context) | 2 | Finance |
| `compute_toll` | `toll_rate_bands` (+ `vessels` with a vessel_id) | 1 | Finance / Operations |
| `search_documents` | Qdrant chunks, per chunk (§4) | per chunk | per chunk |
| `suez_transits` (IMF PortWatch), `web_search` (Tavily news) | public external sources | 1 | Operations |
| `sea_route` (Stage 2, ADR-055) | `ports` + the local `searoute` library | 1 | Operations |
| `vessel_params` (Stage 2) | `vessel_performance`, `bunker_prices` (+ `vessels` and the voyage file with a vessel_id) | 1 | Operations |
| `voyage_status` (Stage 2) | `vessels` (MMSI), MongoDB `ais_positions`, the voyage file, `ports`; fixes up to the run's clock | 1 | Operations |
| `marine_weather` (Stage 2; Open-Meteo) | public external source | 1 | Operations |
| `route_advice` graph (Stage 2, ADR-057; CLI `Route_advice.py`) | `vessel_params`, `sea_route`, `compute_toll`, `suez_transits`, `web_search` with the asking user | 1 | Operations (every employee may ask; each tool checks the user; a refused input → `not_permitted`, no number) |
| `agent_state` threads `route_advice:<employee>:…` | one route question and its answer | 1 | Operations (no employee reads the table directly; `Route_advice.py show` / `list`; deleted after 30 days) |
| `voyage_watch` graph (Stage 2, ADR-058; CLI `Voyage_watch.py`) | `voyage_status`, `vessel_params`, `marine_weather`, `suez_transits` (+ `vessels` names) with the run's user; the tool `voyage_eta` | 1 | Operations (every employee may read the alerts; the scheduled run identity is an Operations manager, `WATCH_RUN_AS`; a refused user → `not_permitted` before any read) |
| `agent_state` threads `voyage_watch:<as_of>:<n>` + `reports/voyage_watch/<thread>.json` | one watch run: ETAs, alerts, the brief | 1 | Operations (read through `Voyage_watch.py alerts --as` / `show` / `list`, which check the identity; threads deleted after 30 days, the files kept — save only) |
| `voyage_eta` (supervisor product tool, Phase 12; `tools/eta.py`) | `voyage_status` + `vessel_params` resources; fixes up to the run's clock | 1 | Operations |
| `watch_alerts` (supervisor product tool, Phase 12; `tools/watch.py`) | one saved run file of `reports/voyage_watch/`: the latest at or before the run's clock (never chosen by the model); since c1 each alert carries its vessel's `customer_id` (from `vessels`, a level-1 id) and one count row per customer | 1 | Operations (every employee; the identity is checked; ids only, never a customer's name or money) |
| `arrival_advice` graph + supervisor product tool + CLI `Arrival_advice.py` (JIT arrival plan) | `voyage_status`, `vessel_params`, `port_call_messages`, `sea_route` / `compute_toll` (the Cape option), `marine_weather`, `suez_transits`; fixes and RTA messages up to the run's clock | 1 | Operations (every employee may ask; the tools check the run's user before any read) |
| `fleet_customers` (supervisor product tool, Phase 12; `tools/fleet.py`) | `vessels` (`vessel_id`, `vessel_name`, `vessel_type`, `customer_id`) | 1 | Operations (ids only: the customer's name, terms and money stay in `finance_kpi`, level 2 / Finance) |
| `route_advice` tool (supervisor product tool, Phase 12, P12-2; `tools/products.py`) | the `route_advice` graph above, one thread per call (metadata `trigger: supervisor`), with the asking user and clock | 1 | Operations (a refused user → `not_permitted` before any model call, no row) |
| `agent_state` threads `ask:<employee>:<as_of>:<n>` (the supervisor, Phase 12 S4; CLI `Ask.py`) | one question, its routing (the refused part) and its checked answer — may hold the asker's finance figures | as the answer's data (≤ the asker's access) | the asker and the CEO only (`Ask.py show` / `list` check the identity); deleted after 30 days by the shared retention, archived first |
| Skills (`pipelines/agents/skills/`) | instructions only, no data | — | — |
| `weekly_pack` approval (ADR-050) | a decision on a pack (approve / edit / reject), no data | — | Finance managers and the CEO only, checked in PostgreSQL at every decision; anyone else is refused and logged |

## 5. Synthetic company documents (planned)

| Source | Level | Owner department | Why |
|---|---:|---|---|
| Synthetic incident reports (linked to our vessels) | 2 | Operations | internal operational incidents |
| Synthetic bills of lading (customer names, commercial terms) | 2 | Operations | commercially sensitive |

## 6. Open points

- Employees have no active/inactive status; the column is dropped (ADR-017).
- Exception cases (temporary permissions, conflicting duties) from the early design are not modelled.
