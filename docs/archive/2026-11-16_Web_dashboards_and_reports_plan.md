# Web dashboards parity, export, breakdowns, the pack decision bar and the tab names — plan

> **Implementation record — Status: IMPLEMENTED (2026-11-16).** Phases 1–5 done and amendment 1 (§4a) done.
> - **Data and API:** migration 029 (`finance.kpi_weekly_breakdown`, M18). The API adds the breakdown, the page
>   workbook and the per-figure Excel / CSV export, each with an audit row.
> - **Dashboards:** the five week pages gained Power BI's missing visuals, forms chosen by the data's job, highlights,
>   and a download on every card.
> - **Reports:** one decision bar for the whole pack, the report-week marker in the preview, an answer box for the
>   request reader's question, and Revise merged into Request. The tabs are renamed Reports / Dashboards.
> - **Parity (Phase 5):** on **W17** instead of W16 (owner: "we did W17"; W16 was matched by the frontend plan).
>   Power BI = the views = the API on 249 values, 0 differences; the web shows them rounded only (stack test, 16 / 16).
> - **Checks:** full-data `Api_check` 12 / 12; `npm run check` ✅.
> - **Live packs:** W17 tested through the web, then approved and published.
> - **Side changes:** three V9 Validator rules (ADR-051 amendment 13); the real ADR-052 Stage 1 run for them was
>   superseded by the targeted-revise plan's run `tr1` ("tie: keep").
> - **Deviations:** the URLs stay `/packs` and `/finance`; no SCNT-tons total card; parity on W17.
> - **ADRs:** ADR-069 + amendment 1 + closing note; ADR-047 note; ADR-051 amendment 13.

**Status: APPROVED (2026-11-15, owner, clickable answers: D-WD-1 "week pages only", D-WD-2 Excel, D-WD-3 everyone who sees the dashboard, D-WD-4 "Break down by")** — written PROPOSED the same day on the owner's request (Egyptian Arabic, summarised): (1) match the web's
finance dashboard to the Power BI dashboard, "many things are missing in the web"; (2) an export button for the web
dashboard's numbers, downloaded in an organised way, allowed to every analysis employee; (3) categories on the visuals
for flexibility in what is shown; (4) a clear approval of the **whole** weekly pack — last time the owner approved
from the last slide and could not tell whether it applied to the slide or the report; (5) rename the "Weekly pack" tab
to **Reports** and "Finance" to **Dashboards**; (6) a question: does the project use Vercel, and where?

Touches ADR-047 (KPIs only in `finance` SQL views), ADR-048 (Power BI), ADR-060 + the Frontend plan (D-FE-7: the web
finance pages = Power BI for a hand-checked week), ADR-064 (the API), ADR-006 / `docs/rbac_mapping.md` (who reads
`finance.*`). Runs before the rest of `Model_flexibility_plan.md` (its Phase 1 has only an unwired file, see there).

## 0. Answer to (6): Vercel (existing, verified 2026-11-15)

Vercel is **not** used to host, build or deploy anything: no `vercel.json`, no `@vercel/*` package in
`web/package.json`, no Vercel account or project; the web app is built by its own `web/Dockerfile` and served by
`docker compose` on `127.0.0.1:3000` (Frontend plan §11). The name appears in three places only:
- **Next.js** itself (the web framework, open source, made by Vercel) — it runs in our container, not on Vercel.
- **Geist / Geist Mono** fonts (OFL licence, by Vercel) — `web/design/MASTER.md`.
- Two **Claude Code skills** copied at a pinned commit, `.agents/skills/vercel-react-best-practices` and
  `vercel-composition-patterns` (Frontend plan §9a): written advice on React code, read by Claude while coding; nothing
  of them runs in the app.

## 1. What the web is missing against Power BI (existing, read 2026-11-15)

Power BI: `powerbi/PortPilot_Finance.Report` (8 pages). Web: `web/src/components/finance/FinanceDashboard.tsx` (6 tabs,
data from `GET /api/v1/finance/{weekly|category|customers|overdue|trend}` and `/invoice-audit`).

| Power BI page | Power BI visuals | In the web today | Missing in the web |
|---|---|---|---|
| Overview | 6 KPI cards, Billed vs Budget column, 13-week variance card, invoices billed, top-10 share, warm-up note | 6 KPI cards, 13-week billed / budget / collected line | Billed vs Budget column, 13-week variance, invoices billed, top-10 share, warm-up note |
| Revenue | cards Invoice Count / Revenue / SCNT tons; by toll band; billed vs budget by category; top 10 routes; laden vs ballast donut; 13-week billed vs budget | billed vs budget by category | the three cards, **toll band**, **routes**, **laden / ballast**, 13-week billed vs budget |
| Receivables | 4 cards; AR by aging; DSO 13 weeks; 5 cards (DSO best / delinquency, due-week collected %, overdue new / paid); overdue list (8 columns) | AR by aging, 4 cards, overdue list (4 columns) | Collected + DSO cards, **DSO trend**, DSO split, due-week collected %, list columns bucket / due date / vessel |
| Customers | top 10 bar, top 10 vs others donut, 3 cards, table (10 columns) | table (6 columns) | the **bar**, the **donut**, the 3 cards, columns rating / terms / on-time % / AR-to-billed % |
| Exceptions | status card, 3 cards, findings table (10 columns, all of 2025) | 4 cards, findings table of the week (4 columns) | week status, the year-wide table option, columns billed / expected / evidence / duplicate of / date |
| Executive (year, no slicer) | rolling 13-week billed vs budget, customer-risk scatter, AR 90+ by customer, DSO split area | 4 cards of the week + this week's pack | **all four year-wide visuals** |
| Smart View | measure-by-category picker, trend-series picker, compare week (category and AR buckets) | — (the Charts page is a model-chosen view, not this) | **the pickers and the compare week** = request (3) |
| Approved Pack | approved summary, trend and variance of the week | the pack panel inside Executive | its own tab |

## 2. Design (PROPOSED; assumes the recommended answers of §4)

### 2a. Data — migration `029_kpi_breakdowns.sql` (applied by the owner)

ADR-047 keeps every number in a `finance` SQL view; Power BI's DAX on this page set is plain sums over the star
(`Revenue SDR = SUM(Invoices[amount_sdr])` …), so the views below are the same sums, written once in SQL:
- `finance.kpi_weekly_breakdown (report_week, dimension, member, invoices_billed, billed_sdr, scnt_tons, share_pct)`
  — long format over `fact_invoice` by `invoice_report_week`; `dimension` ∈ vessel_category, toll_band, route,
  priced_condition (laden / ballast), customer_segment, customer_country, credit_rating. One view serves every
  "break down by" choice of request (3). Guard: for each week and dimension the members sum to `kpi_weekly.billed_sdr`.
- `finance.kpi_customer_risk (customer_id, customer_name, credit_rating, revenue_2025_sdr, mean_days_late,
  payments_paid)` — the Executive scatter (DAX `Mean Days Late`, `Revenue 2025 SDR`).
- `finance.kpi_ar_customer (report_week, customer_id, customer_name, aging_bucket, amount_sdr)` — AR 90+ by customer
  and receivables broken down by customer.
- The year-wide Executive lines (rolling 13-week billed / budget, DSO split) are already rows of `finance.kpi_weekly`;
  the API reads all its weeks at once (no new view).
- Grants as the other `finance` views (the API, the BI login); `docs/finance_metrics.md` gains one definition each.

**Not added to the agents' `finance_kpi` tool.** Its `dataset` list is part of the tool schema sent to the models, so
a new value would change the cache key of every tools-role call and make the next evaluation re-spend its quota. The
API reads the new views through its own small reader with the same RBAC gate (`_gate`) and the same `db` helper.

### 2b. API (`pipelines/api/routers/finance.py`)

`GET /finance/breakdown?week&dimension`, `GET /finance/year`, `GET /finance/customer-risk`,
`GET /finance/ar-customers?week`, and `GET /finance/export?week&page` → one **.xlsx** workbook: a sheet per visual of
the page (its rows exactly as the view gives them, headers in English, SDR with two decimals) + an **About** sheet
(page, week, exported by employee id, time in Cairo, each sheet's source view and filter, a pointer to
`docs/finance_metrics.md`). Access = the same rule as the dashboard (§4 D-WD-3), checked in the API; every export
writes one `audit_log` row. OpenAPI snapshot and the generated web client refreshed.

### 2c. Web — the **Dashboards** tab (was Finance)

Tabs = the 8 Power BI pages: Overview, Revenue, Receivables, Customers, Exceptions, Executive (year), **Explore**
(Smart View), Approved pack — each with the visuals of §1 that are missing today. Every chart card whose data has a
category gets a **"Break down by"** select (the dimensions of 2a) and, where it fits, a **measure** select (billed /
invoices / SCNT tons); Explore adds a **compare week**. The choice lives in the URL, so a link reopens the same view.
An **Export** button in the page header downloads the workbook of 2b for the shown week and page. Numbers stay
receipts (source on hover); charts keep their table for screen readers; EN + AR, desktop + phone.

### 2d. Web — the **Reports** tab (was Weekly pack): one decision for the whole pack

The API never had a per-slide approval: `approve` / `reject` always decide the whole pack. The confusion is the page:
the Approve / Reject buttons sit at the bottom of the side panel that edits **the current slide**. Change (UI only):
- a **pack decision bar** at the top of the review, always visible: "Decision for the whole pack — week W, N slides"
  with **Approve the whole pack** and **Reject**; Approve opens a confirmation that names the week, the slide count
  and "this publishes the deck"; Reject needs its comment there.
- the side panel becomes **"Changes to slide N"** (edit the slide's words, add a bullet, revise with a steer) — no
  approve / reject inside it any more.

### 2e. Names and links

Menu: **Reports** (`/reports`) and **Dashboards** (`/dashboards`); `/packs` and `/finance` redirect to them (old links,
bookmarks and the publication e-mail texts keep working). API paths unchanged. The "Charts" tab stays as it is.

## 3. Phases

| # | Work | Done when |
|---|---|---|
| 1 | Migration 029 + `docs/finance_metrics.md`; `Finance_views_check.py` gains a phase: breakdown sums = `kpi_weekly`, risk and AR-by-customer = a pandas reference | owner applies 029; snapshot refreshed + read-only audit; the check ✅ |
| 2 | API endpoints + export + audit row; `Api_check`-style fixture tests for access (Finance employee, other-department employee refused, manager, CEO) and the workbook's sheets; OpenAPI + Orval | the checks ✅, `tools/openapi_snapshot.py --check` ✅ |
| 3 | Dashboards: 8 tabs, the missing visuals, break-down / measure / compare pickers, Export button | `npm run check` ✅, Playwright EN + AR desktop + phone, axe 0 serious |
| 4 | Reports decision bar + renames + redirects | the same, plus a test that Approve is reachable only from the bar and confirms |
| 5 | Parity: one week (W16) — every web number = Power BI (DAX through the Power BI MCP, Desktop opened by the owner) = the view; ADR-047 note, ADR-060 amendment, ARCHITECTURE, ROADMAP; archive | the parity table in this plan, the owner's one commit |

## 4. Owner decisions (asked once, clickable, recommendation first)

| # | Question | Recommended | Alternatives |
|---|---|---|---|
| D-WD-1 | How much of Power BI | all 8 pages, incl. Executive (year) and Explore | the week pages only |
| D-WD-2 | Export format | one Excel workbook per page (sheet per visual + About sheet), built in the API (`openpyxl` added with uv) | a ZIP of CSV files (no new library); per-chart CSV in the browser |
| D-WD-3 | Who may export | everyone who may open the dashboard (the `finance_kpi` rule: Finance employees, every manager, the CEO) | Finance department + CEO only; a new "Analysis" department (no such department exists: Operations, Customs, Finance, HR, IT) |
| D-WD-4 | The categories | "Break down by" on the charts from one breakdown view (category, toll band, route, laden / ballast, segment, country, rating) + measure + compare week | only Power BI's two Smart View pickers |

## 4a. Amendment 1 — visual variety, highlighting, per-figure export (owner comments 2026-11-15, APPROVED + IMPLEMENTED 2026-11-15)

The owner, after phases 1–4: (1) every visual is one colour and one shape — he wants chart types and colours that
fit the data and the important things highlighted; (2) the export must be the numbers of one visual or table, not the
whole page. Designed with the `dataviz` skill (form by the data's job, emphasis, the palette validator) inside
`web/design/MASTER.md` (blue / white, light only, status = icon + text). The numbers do not change: same views, same
receipts, the web draws widths and picks the highlighted item by a fixed rule (largest, below budget, oldest bucket,
watchlist, the report week) — no new figure is printed that a view did not give (ADR-047).

**D-WD-5 — form and colour by the data's job.**

| Visual | Today | Amended form | Highlight |
|---|---|---|---|
| KPI tiles (every page) | number + text change | number + a coloured change (arrow + "+x %", green when the move is good for the business, orange when bad — direction is a fixed rule per KPI) + a 13-week sparkline from `trend` | the bad moves |
| Overview "billed vs budget" | a one-bar bar chart (an anti-pattern) | a **bullet bar**: billed bar against a budget tick, the variance % from the view printed | below budget → orange |
| 13-week trends | three lines | **bars + line**: billed bars, budget dashed line, collected line; DSO as an **area** | the report week's bar full colour, the other weeks muted |
| Revenue by vessel category | grouped vertical bars | **horizontal bullet bars** (billed bar, budget tick), largest first | categories below budget in orange, the rest blue |
| Breakdowns: few members (≤ 4, the validated categorical slots; e.g. laden / ballast, segment) | vertical bars | a **segmented share bar** (each part's `share_pct` printed on it) + a ranked list | — (identity: categorical blue / teal / amber / violet) |
| Breakdowns: more members (route, country, category …) or a compare week | vertical bars | **ranked horizontal bars** (long names readable, also on phones) | the largest member blue, the rest muted; with a compare week the other week is a light bar beside it |
| Receivables by age | five equal bars | one **stacked aging bar** (ordinal blue ramp, current → 61–90) + the bucket list | 90+ in the `marker` orange |
| DSO split | three tiles | a **stacked bar** of best + late-payment days, the view's DSO at the end | the late-payment part orange |
| Due this week, collected % | a tile | a **meter** | below 50 % orange |
| Top 10 customers | vertical bars | **ranked horizontal bars** | watchlist customers orange with a "watch" label |
| Exceptions | four tiles | tiles + a **meter** "flagged of checked" + the difference column drawn as a small **diverging bar** (over / under-billed) | manual-review rows marked |

**D-WD-6 — export per figure.** Every chart and table card gets a **Download** button (Excel one sheet + About, or
CSV) for its own rows exactly as the view gave them, with its source view and filter (and, for a breakdown, the
dimension and the compare week's rows). Built in the API (`GET /finance/export?week&figure=…[&dimension&compare&ytd]
&format=xlsx|csv`), the same access rule (D-WD-3), one `audit_log` row per download.

| # | Question | Recommended | Alternatives |
|---|---|---|---|
| D-WD-5a | Chart forms | the table above (form by the data's job, dataviz rules) | the same + donut / pie for parts of a whole |
| D-WD-5b | Colour and highlight | emphasis: the item that matters in colour, the rest muted; KPI changes green / orange by direction (icon + sign, never colour alone) | a categorical colour per series on every chart |
| D-WD-6a | Where the per-figure file is built | the API (Excel one sheet + CSV, audit row, access checked) | the browser (CSV of the rows on screen, no audit row) |
| D-WD-6b | The page-level "Export to Excel" button | removed (only per figure) | kept beside the per-figure buttons |

**Owner answers (2026-11-15, asked once):** D-WD-5a the table above, D-WD-5b emphasis, D-WD-6a the API — as
recommended; **D-WD-6b = keep the page button** beside the per-figure buttons (not the recommendation).

## 5. Out of scope, risks

- Out: editing Power BI itself; new KPIs that Power BI does not have; changing who may decide a pack; the agents'
  tools and prompts (their cache keys stay as they are).
- Risk: a breakdown member list too long for a chart (routes) → top 10 + "other", the full list in the table and the
  export. Risk: Excel opening SDR as text → numbers written as numbers with a number format, not strings.

## Progress / deviations

- 2026-11-15 — plan written PROPOSED; facts read: the 8 Power BI pages (visuals and fields from the PBIR files), the
  web dashboard, the API's finance router and the `finance_kpi` datasets, the pack review and decision panel, the
  departments in the synthetic generator.
- 2026-11-15 — **APPROVED** by the owner. **D-WD-1 = the week pages only** (not the recommendation): Overview, Revenue,
  Receivables, Customers, Exceptions get the missing visuals; the year-wide Executive visuals, the Explore (Smart View)
  tab and a separate Approved-pack tab are **not** built (the existing Executive tab stays as it is). Consequence for
  §2a: `kpi_customer_risk` and `kpi_ar_customer` are dropped (they served Executive only); migration 029 holds the
  breakdown view alone. D-WD-2 Excel (openpyxl), D-WD-3 the `finance_kpi` rule, D-WD-4 break down + measure + compare
  week, as recommended.
- 2026-11-15 — **Phases 1–4 done** (handoff):
  - **Phase 1:** `db/migrations/029_kpi_weekly_breakdown.sql` — dry run in a rolled-back transaction (0 mismatches
    against `kpi_weekly` on every week × dimension), then applied (BEGIN / CREATE VIEW / 9 COMMENT / 2 GRANT /
    COMMIT, `ANALYZE`); `db/schema_snapshot.sql` refreshed (insertion only, +115 lines); `db/audit/2026-11-15_after_029_report.txt`
    reaches END with 0 errors. `docs/finance_metrics.md` M18. `Finance_views_check.py` Phase 8 = an independent pandas
    reference from the base tables: 2,820 rows, 52 weeks × 7 dimensions, members = `kpi_weekly` (largest gap 0.00 SDR),
    reviewed snapshot of week 16 (Laden 2,634,930.15 SDR, top band "The Rest"); all 9 validation lines ✅.
  - **Phase 2:** `pipelines/api/finance_views.py` (breakdown reader + the workbook) and two routes in
    `pipelines/api/routers/finance.py`; `uv add openpyxl==3.1.5` (+ et-xmlfile 2.0.0). The workbook per page: About
    + a sheet per visual (Revenue: category vs budget, six breakdowns, trend; Exceptions: the audit's own totals +
    findings). Smoke through the router on the live views (auth dependency overridden, `audit.record` captured, not
    written): breakdown 200 / bad dimension 422; the six pages' workbooks open with openpyxl; an Operations employee
    gets 403 on export and breakdown, an Operations manager 200; audit rows `export:<page>` / `export`. Found and
    fixed on the way: Excel refuses "/" in sheet names (500 on Revenue). `Api_check.py` Phase 11 gained the same
    assertions (runs on the full-data clone, owner gate). OpenAPI 36 paths, lint 0 / 0.
  - **Phase 3–4 (web):** client regenerated (Orval) + BFF allow-list; `components/finance/Breakdown.tsx` (dimension /
    measure / compare week, URL-kept, top 10 + full table); the five week pages gained the missing visuals of §1
    (Overview: billed vs budget, 13-week variance, invoices, top-10 share, warm-up note; Revenue: three cards, four
    breakdown cards (toll band, routes, laden / ballast, segment), 13-week billed vs budget; Receivables: collected,
    DSO, DSO split, due-week collected, DSO trend, list columns vessel / due date / age; Customers: three cards, top-10
    bar, a breakdown card, table columns rating / terms / AR-to-billed / on-time; Exceptions: this week / year to date,
    columns date / billed / expected / duplicate of); "Export to Excel" in the header. Reports: the "Decision for the
    whole pack" bar (Approve → a confirmation naming all N slides and the week; Reject needs its comment), the side
    panel is "Changes to slide N" without approve / reject. Tabs Reports / Dashboards; `/reports`, `/dashboards`
    redirect. Found and fixed on the way: two quick picker changes overwrote each other (the choice is now state,
    mirrored to the URL); the stale-tab test needed its wait for the review. `npm run check` all ✅ (Playwright 3
    new dashboard tests + the updated approval tests, EN + AR, desktop + phone, axe 0 serious); one unrelated
    sign-out flake in one run, passed 3 / 3 alone.
  - **Deviations:** §2e — the URLs stay `/packs` and `/finance` (moving the route folders would touch every link and
    bookmark for no visible gain; the new names redirect). No SCNT-tons total card: no view holds a weekly total of
    tons, and the web adds no arithmetic — tons are a measure of every breakdown card and a column of the export.
  - **Open (owner):** Phase 5 parity — open Power BI Desktop (`powerbi/PortPilot_Finance.pbip`) and the API
    (`Serve.py`) so Claude reads week 16 by DAX through the Power BI MCP and compares with the web; the full-data
    `Api_check` (clone, see the stabilization plan); a look at the Reports bar on the next real pack (W17).
- 2026-11-15 — **Amendment 1 (§4a) implemented** (side session; owner answers D-WD-5a/5b/6a as recommended, D-WD-6b keep
  the page button):
  - **API:** `finance_views.figure_file` + `GET /finance/export/figure?week&figure&format=xlsx|csv` with `page` (KPI
    tiles), `dimension` + `compare` (breakdown), `ytd` (audit), `limit` (ranked lists); the workbook's About writer
    shared with the page export (`_xlsx`), the audit totals shared (`_audit`); 422 for a breakdown without its
    dimension; one `audit_log` row `export:<figure>`. Live smoke on W16: 8 figures × xlsx / csv open and hold the
    view's rows (e.g. route 11, overdue 32, trend 13, laden / ballast vs W15 = 4 rows), an Operations employee refused.
    `Api_check.py` Phase 11 + 3 assertions (breakdown + compare = 2 × rows, category CSV = the tool's rows with
    `source_view,source_filter`, 422, 403) — runs on the clone at the owner's gate. OpenAPI 37 paths, Orval + BFF
    allow-list regenerated, lint ratchet 0 / 0.
  - **Web:** `components/viz/forms.tsx` (Delta, BulletBars, RankedBars, SegmentBar, Meter, DivergingCell, AGING_TONES),
    `SeriesChart` kinds `combo` / `area` + `highlight`, `components/finance/FigureCard.tsx` (card + "Download: Excel ·
    CSV"); the five week pages and Executive use them (§4a table); `Breakdown.tsx`: ≤ 4 members → segmented share bar,
    more or a compare week → ranked bars (largest of the shown measure in colour). Palette checked with the dataviz
    validator: categorical blue / teal / amber / violet pass on white; the aging ramp passes as ordinal. Found and
    fixed: white text on the blue fill is 4.42:1 (axe) → share labels sit on a white pill; on phones the sideways
    tables are now focusable regions (axe `scrollable-region-focusable`). The page button reads "Export whole page".
  - **Proof:** `npm run check` all ✅ (Playwright 140 passed incl. 2 new dashboard tests — forms + emphasis + axe on
    every week page, desktop + phone; per-figure download links and file names); one earlier full run had a single
    failure that did not repeat in the next two full runs. Screenshots of each week page inspected
    (`Notebooks/_scratch/dashboards-<page>-<desktop|mobile>.png`). Numbers unchanged (same views, no new arithmetic):
    the W16 parity stands.
  - **Owner step:** rebuild the web container — `docker compose up -d --build web` (the API change needs the API
    process restarted as well, `Serve.py`, if it is running).
- 2026-11-15 — **Reports preview: the deck's report-week marker** (owner: "ظبط الدنيا", after asking whether Reports
  needs a change). The Reports page stays a faithful preview of the PPTX (no new forms or colours there: they belong
  to the deck, its Validator and the evaluation baselines). One gap closed: the deck marks the report week on its trend
  line (`render.py` `highlight`, a 10 px circle in `S.HIGHLIGHT` = `#EB6834`) and the API already sends it in
  `charts_drawn`, but `PackChart.tsx` ignored it. Now `SeriesChart` (kind `line`) draws that circle on the first series
  in `--marker` (axis padding so the end point is not clipped), with the line "<week> is the report week." under the
  chart. Mock pack chart `highlight: 5`; `packs.e2e.spec.ts` asserts the marker and the caption (+ a screenshot,
  inspected). `npm run check` all ✅. No API or deck change.
- 2026-11-16 — **Live W17 pack + three Validator rules** (owner: "start W17", then "fix it so the model does not
  make it again, then give me a test"). `Weekly_pack.py run --week 17 --as 6` → `weekly_pack:live:2025-W17:1`
  waiting for approval (DEGRADED: 2 checks after rewrites, bullets dropped by code). Review found three wrong sentences
  the Validator let through (slide 4 title "exceeded budget" with the week −12.49 %; slide 6 title "declined by down
  8.5 %"; slide 3 total collections compared with what fell due). Fixed in code: V9 rules 2b (budget words), 9, 10 —
  ADR-051 amendment 13; `Deck_check` 8 / 8 (+3 planted classes from W17), `Weekly_pack_check` 9 / 10 (Phase 5 = real
  models, skipped), lint 0 / 0; the W17 draft re-validated shows exactly these three. Not decided: the pack (the
  owner, from the web Reports page — the last gate of this plan); the real Stage 1 run for ADR-052 (quota).
- 2026-11-16 — **Reports: answering a question the request reader asks back** (owner: after "Understand my request"
  the reader asked a question and there was no box to answer it). The request API keeps no conversation, so the
  panel now shows "Your answer" under the question (focused) and "Send my answer" sends the request again with the
  question and the answer joined (`withAnswer` in `DecisionPanel.tsx`: request and answer kept whole, the question
  shortened to fit the API's 500 characters); that combined text is what Confirm sends. Mock: "look again" without an
  answer asks back; `packs.e2e.spec.ts` + 1 test (question shown, no Confirm, answer box focused, combined request,
  then the steps and Confirm). `npm run check` all ✅. ADR-051 amendment 13 written in `docs/decisions.md`.
- 2026-11-16 — **W17 tested and published; Revise merged into Request** (owner: "check it yourself, run every test,
  then approve"; answers: remove the slide-9 repeat with an edit first, merge Request and Revise, revise only the
  related slides). Checks on the live W17 draft after the owner's revise: the new Validator passes it; 29 / 29 deck
  numbers = the views read again through the read-only tools (a 30th, −6.85 → −6.9 %, is the deck's half-away-from-zero
  rounding); full-data `Api_check` on the clone 12 / 12 (incl. the per-figure export assertions); `Deck_check` 8 / 8,
  `Weekly_pack_check` 9 / 10, `npm run check` ✅. Edit as employee 6 (slide 9's "(the four weeks before: 37.4)"
  removed: code's bullet 23 states it) → passed → **approved and published**
  (`reports/2025-W17/_publications/f231bb6a1fc747b5817a4f8721efd1cb`). Web: the Revise tab is gone — an analysis
  change (a caveat, a point to look at again) is asked in words in Request, which already maps words to the same
  edit / revise / chart steps and shows how many re-drafts are left; Edit and Chart stay (no model call). Mock: a
  "caveat" request → one revise step; the chart + caveat test now goes through Request. `npm run check` ✅.
  **Next (owner's choice, its own plan):** a revise re-drafts only the slides related to what changed (slide 2
  follows) and keeps the earlier edits; fewer code fallbacks — then the page's two banners ("drafted again …",
  "some texts were written by code") can go.
- 2026-11-16 — **Phase 5 parity on week 17 — the plan closes** (owner: "continue with what is left", then "we did
  W17"; Power BI Desktop opened by Claude, the PostgreSQL sign-in typed by the owner). Week 17 instead of 16: it is
  the last published pack, and W16 was already matched by the frontend plan (D-FE-7). Three readers, one script
  (scratchpad, not kept): Power BI's measures by DAX through the Power BI Modeling MCP, the `finance` views read
  directly, and the API's own `finance_kpi` rows as a Finance manager (employee 6).

  | Figure (W17) | Values compared | Power BI = views | API = views |
  |---|---|---|---|
  | `kpi_weekly` row (billed 4,951,237.35; collected 5,569,636.85; AR 37,981,157.17; overdue 9,383,218.61; DSO 51.4; budget variance −12.49 %; 13-week variance −6.85 %; top-10 share 59.84 %; due-week collected 56.09 %; on time 43.86 % …) | 23 fields × 2 | ✅ | ✅ |
  | Categories billed / budget / variance | 13 × 3 × 2 | ✅ | ✅ |
  | Receivables by age (current, 1–30, 31–60, 61–90) | 4 | ✅ | — (no API dataset; the receivables card reads `kpi_weekly`) |
  | Top 5 customers: billed 13w, share, AR, overdue | 5 × 4 × 2 | ✅ | ✅ |
  | Trend weeks 5–17: billed, collected, budget | 13 × 3 × 2 | ✅ | ✅ |
  | Overdue list rows (27) and audit findings (0) | 3 | ✅ | ✅ |
  | **Total** | **249** | **0 differences** | |

  The web layer: new stack test `web/tests/stack/parity.stack.spec.ts` — a Finance manager on the real API over the
  full-data clone; the BFF's `weekly` row for W17 = the view's values exactly, and the tiles show them rounded only
  (4.95M, 5.57M, 37.98M, 9.38M, 51.4 d, 16; receivables 2.47M / 3.33M; "Billing was 12.5% below the week's budget.").
  `ops/tests/run_web_stack.ps1` 16 / 16 (first run: the test's own sign-in waited for a path with a query string —
  fixed by signing in on `/finance` first). ADR-047 note, ADR-069 closing note, ARCHITECTURE (the figure export and
  parity). Every done-when met; the owner's one commit is left (with every plan closed).
