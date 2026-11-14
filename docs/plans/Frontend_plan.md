# Plan — the NileGate web frontend (ADR-060)

**Status: APPROVED (2026-11-06, owner: "موافق")** — written PROPOSED the same day; the owner asked for the knowledge
graph to be refreshed before any step (Progress / deviations).
**A second active plan, on purpose:** `docs/plans/` normally holds one active plan; the owner asked on 2026-11-06 for
this plan to be written **in parallel** with `docs/plans/Pack_approver_additions_plan.md` (APPROVED 2026-11-06, being
implemented in another session; Phases A–B done). Nothing here is implemented while that plan edits `pipelines/api/`,
`pipelines/agents/` and `pipelines/scripts/agents/` (see §11, F0 ordering).

Touches ADR-060 (+ amendments 1–2), ADR-064 (the API), ADR-065 (conversation memory), ADR-062 (observability layers),
ADR-063 (CI, lint ratchet, Dependabot), ADR-048 (Power BI stays Desktop) and the approver plan's §2c–§2d (chart
catalogue, views). Sources read: `ARCHITECTURE.md` §7, `docs/ROADMAP.md` (Frontend row), `docs/decisions.md`
ADR-060 / 064 / 065, `docs/archive/2026-11-05_FastAPI_plan.md` §3 / §5 / §6 / §7 / §9, `docs/api/openapi.json`,
`pipelines/agents/graphs/models.py` (approval + view models), `pipelines/agents/deck/charts.py` (catalogue),
`pipelines/api/config.py` / `app.py` / `middleware.py` (CORS, CSP).

---

## 0. Owner decisions

Asked once, up front, 2026-11-06, as clickable choices (recommendation first). All four answered **as recommended**.

| # | Decision | Answer |
|---|---|---|
| F1 | Where the login token lives in the browser | **A cookie held by Next.js (a BFF)**: the Next.js server keeps the API's bearer token in an `httpOnly`, `SameSite=Strict` cookie; the browser only talks to its own origin and never sees the token (XSS cannot read it). Cost: CSRF protection (§4.3) and SSE passed through Next.js (§5). Rejected: token in memory only (re-login on every reload), `sessionStorage` (readable by any XSS) |
| F2 | Untyped responses in the OpenAPI schema | **Response models in the API first** — a small backend phase **F0** (§11): one pydantic model per response and a discriminated union per SSE event, so Orval generates real types and the CI catches a broken contract. Rejected: hand-written zod in the frontend only (the contract in two places) |
| F3 | Chart library for `ViewSpec` (and the pack's chart preview) | **Recharts 3.10.1** (MIT, SVG, the base of shadcn/ui charts): SVG lets Playwright read the drawn values and compare them with the `ViewSpec` number by number. Rejected: Apache ECharts 6.1.0 (canvas: values not in the DOM; much larger), Chart.js 4.6.1 (canvas; needs a React wrapper) |
| F4 | Commits | **One commit when the whole plan closes**; the owner commits (no AI attribution in git text) |

**Plan defaults (not asked; the owner may change any of them when approving):**

| # | Default | Why |
|---|---|---|
| F5 | The app lives in `web/` at the project root (its own `package.json`, `package-lock.json`, `.npmrc`) | keeps npm out of the Python tree; one Dependabot / CI path |
| F6 | ~~Default locale Arabic (RTL), English one click away~~ → **superseded by D-FE-6 (owner 2026-11-06): the interface is English; answers follow the language of the question (`dir="auto"`)**; Latin digits everywhere | numbers stay identical to the deck / Power BI |
| F7 | Docker Compose gets the **`web` service only** now; the API stays on the host (`Serve.py`) | the API shares file locks (`llm_cache/`, ADR-064 C3), `reports/` and the 2.2 GB bge-m3 model with the scheduled CLIs on the host; a cross-OS bind mount would weaken those locks. "Compose for all services" stays the ROADMAP's later row |
| F8 | One test runner: `@playwright/test` for E2E **and** for the few pure-logic tests (SSE parser, D1 rules, `ViewSpec` → chart props) — no Vitest | one tool, already chosen by ADR-060 |
| F9 | No map in route advice (table + text); a map is a later option (MapLibre + a free tile source with its usage policy) | the API returns no geometry today |
| F10 | Frontend error reporting to Sentry **deferred** (trigger: the UI used by someone other than the owner); browser debugging stays the Chrome DevTools MCP (ADR-060 amendment 2) | ADR-062 keeps one tool per layer; the BFF's server errors are logged locally |

---

## 1. Scope and non-goals

**In scope:** a local web UI over the existing API — sign-in, the supervisor chat with streamed run events and
uploads, the weekly-pack approval screen (all approver edit kinds of the approver plan), the views / charts page, route
advice, voyage-watch alerts and runs, the pack approval report; Arabic RTL + English; a generated typed client; the
BFF; tests, CI, a Compose service; the Claude Code tooling of ADR-060 amendment 1 (each reviewed before install).

**Non-goals (and why):**
- **No RBAC or identity decision in the browser** (ADR-060 (2)): the UI hides buttons for comfort only (from `GET /me`);
  the API decides every request (403 / 404 shown as such).
- **No new graph or agent behaviour**; the only backend work is F0 (typing + a test mode, §11).
- **No Power BI embedding** (paid / public, ADR-048, ADR-060 (7)); finance charts in the UI come from `ViewSpec`
  (the same `finance` views).
- **No public or paid hosting**; the UI and the API listen on the loopback only.
- **No model tokens in the stream** (the event contract never sends them, FastAPI plan §5): answers appear whole,
  after the code checks — the UI shows progress (nodes, tools) while it waits.
- **No starting packs or watch runs from the UI** (Task Scheduler does, ADR-054 / ADR-058; the API has no endpoint).
- **No long-term memory across conversations** (ADR-065 (5), deferred), no map (F9), no frontend Sentry (F10).

---

## 2. Endpoints the screens use — what exists and what is planned

**EXISTS** = in `docs/api/openapi.json` today (FastAPI plan, archived 2026-11-05). **PLANNED (approver)** = the
approver plan's Phase E / F. **PROPOSED (F0)** = this plan's backend phase.

| Endpoint | Status | Screen | Typed today? |
|---|---|---|---|
| `POST /auth/login`, `POST /auth/logout` | EXISTS | Login (through the BFF) | `TokenOut` ✔ / logout no body |
| `GET /me` | EXISTS | shell, menus | `Me` ✔ |
| `GET /health/live`, `GET /health/ready` | EXISTS | status badge | ✔ |
| `POST/GET /conversations`, `GET/DELETE /conversations/{id}` | EXISTS | Chat | POST / DELETE / list untyped → F0 |
| `POST /conversations/{id}/questions` | EXISTS | Chat | `RunAccepted` ✔ |
| `GET /runs/{run_id}`, `GET /runs/{run_id}/events` (SSE) | EXISTS | every run | `RunOut` ✔; **event `data` = untyped object → F0** |
| `POST/GET /conversations/{id}/uploads`, `DELETE …/{document_id}`, `POST …/{document_id}/promotion` | EXISTS | Chat (uploads) | upload result untyped (`UploadOut` exists, not wired as response) → F0 |
| `GET /questions`, `GET /questions/{thread}` | EXISTS | History | untyped → F0 |
| `GET /packs`, `GET /packs/{thread}`, `GET /packs/report` | EXISTS | Packs | untyped → F0 |
| `GET /packs/{thread}/preview`, `GET /packs/{thread}/deck` | EXISTS | Packs (PPTX download) | file ✔ |
| `POST /packs/{thread}/decision` with `approve / edit / reject`, `edits`, `comment` | EXISTS | Pack approval | `DecisionIn` ✔ |
| the same with **`revise`**, **`additions`**, **`charts`**, **`analysis_edits`**, **`steer`** | **PLANNED (approver, Phase E)** | Pack approval | the models exist in `graphs/models.py` (`Addition`, `ChartChoice`, `AnalysisEdit`, `ApprovalDecision`) |
| `GET /packs/{thread}` + `insight`, `charts`, `redrafted`, `degraded`; `/packs/report` per-kind counts | **PLANNED (approver, Phase E)** | Pack approval, Report | — |
| `GET /charts/catalogue` | **PLANNED (approver, Phase F)** | Pack approval, Views | `charts.catalogue()` exists in code |
| `POST /views` (`{choice}` → 200 `ViewSpec`; `{question}` → 202 + SSE `done` carries `ViewSpec` or ask-back) | **PLANNED (approver, Phase F)** | Views | `ViewChoice`, `ViewSpec` exist in `graphs/models.py` |
| `GET /finance/weeks` · `GET /finance/{dataset}?week=` (`weekly`, `category`, `customers`, `overdue`, `trend`) · `GET /finance/invoice-audit?week=` | **PLANNED (D-FE-7, approved by the owner 2026-11-06)** | Finance dashboard (§6.9) | thin read-only wrappers over the existing tools `finance_kpi` / `invoice_audit` (their RBAC, their rows) |
| `POST /route-advice`, `GET /route-advice`, `GET /route-advice/{thread}` | EXISTS | Route advice | `RouteIn` ✔; results untyped → F0 |
| `GET /voyage-watch/alerts`, `GET /voyage-watch/runs`, `GET /voyage-watch/runs/{thread}` | EXISTS | Voyage watch | untyped → F0 |
| `GET /packs/{thread}` + **`allowed`** (addition slides, caps left, `revise` left) + **`charts_drawn`** (the drawn series of each chart, from `render.build_spec`) | **PROPOSED (F0)** | Pack approval | so the UI never hard-codes ADR rules and can draw a faithful chart preview |
| OpenAPI `securitySchemes: bearer` | **PROPOSED (F0)** | generated client | today auth is read by hand, not declared |

---

## 3. Architecture

```text
browser (http://localhost:3000)                      Next.js server (web/, Node 24)                 FastAPI (127.0.0.1:8000)
  pages, assistant-ui, TanStack Query  ── same origin ──▶  /bff/* route handlers (the BFF)  ── Bearer ──▶  /api/v1/*
  cookie ng_session (httpOnly, unreadable by JS)          · reads ng_session → Authorization            (RBAC, runs, SSE)
  cookie ng_csrf (readable) → X-CSRF-Token header          · path + method allow-list (from OpenAPI)
                                                           · Origin / Sec-Fetch-Site + CSRF check
                                                           · SSE streamed through, Last-Event-ID passed
                                                           · X-Request-ID passed back
```

- **Next.js App Router**, server components for the shell, client components for interactive screens; `output:
  "standalone"` for the Compose image; `NEXT_TELEMETRY_DISABLED=1` everywhere (Next.js collects anonymous telemetry by
  default).
- **Routes:** `web/app/[locale]/…` (`ar`, `en`): `login`, `chat`, `chat/[conversationId]`, `history`, `packs`,
  `packs/[thread]`, `packs/report`, `views`, `route-advice`, `route-advice/[thread]`, `voyage-watch`,
  `voyage-watch/runs/[thread]`.
- **Data:** TanStack Query for every request (cache, retries only on 429 / 503 with `Retry-After`, never on 4xx);
  the generated Orval client (§7) calls the BFF, not the API.
- **The API is unchanged by the BFF**: it still sees a bearer token; `API_CORS_ORIGINS` keeps its default (the browser
  no longer calls the API cross-origin, so CORS becomes a second line, not the main one).

---

## 4. Authentication, CSRF, CORS, CSP

### 4.1 Flow (F1)
1. `POST /bff/login {email, password}` → the BFF calls `POST /api/v1/auth/login` → sets `ng_session` = the opaque token
   (`httpOnly; SameSite=Strict; Path=/; Secure` — `localhost` is a secure context, so `Secure` works on plain HTTP
   there; `Max-Age` = the token's `expires_at`) and `ng_csrf` = 32 random bytes (readable, `SameSite=Strict`) → returns
   `me` only. **The token never appears in a response body, JS, `localStorage` or a URL.**
2. Every `/bff/*` call: the BFF reads `ng_session` → `Authorization: Bearer …` → the API. `401` from the API → the BFF
   clears both cookies → the UI goes to login (with the page to return to, same-origin paths only).
3. `POST /bff/logout` → `POST /api/v1/auth/logout` (revokes the token in `api.tokens`) → cookies cleared.
4. Who the user is comes only from `GET /me` (role, department, ceiling, products, tools); the request body never
   carries an employee id (ADR-064 (2)).

### 4.2 The BFF's own rules
- **Allow-list:** only the `(method, path template)` pairs of the OpenAPI schema (generated at build time from
  `docs/api/openapi.json`); anything else → 404 without calling the API (no open proxy, no SSRF: the upstream host is
  fixed from `.env` `NILEGATE_API_URL`, default `http://127.0.0.1:8000`).
- Request headers passed: `Content-Type`, `Accept`, `Last-Event-ID`, `X-Request-ID`; never the browser's cookies.
  Response headers passed: `Content-Type`, `Content-Disposition` (PPTX), `Retry-After`, `X-Request-ID`.
- Body limits follow the API's (16 KB JSON, 5 MB uploads) and are also enforced at the BFF.

### 4.3 CSRF (needed because auth is now a cookie — FastAPI plan §6 recorded this)
Three layers: (1) `SameSite=Strict` on both cookies; (2) every unsafe method (POST / DELETE) must carry `Origin` equal
to the app's origin (or `Sec-Fetch-Site: same-origin`); (3) a double-submit header `X-CSRF-Token` equal to `ng_csrf`.
Any failure → 403 before the API is called. GET handlers have no side effects (the API's GETs are reads).

### 4.4 CORS
The browser calls only its own origin → no CORS needed for the UI. The API's allow-list (`API_CORS_ORIGINS`,
default `http://localhost:3000`, never `*`, no credentials) stays as defence in depth.

### 4.5 CSP and rendering model text (ADR-060 (3))
- Set by the Next.js request proxy on every page, **with a per-request nonce**: `default-src 'self'; script-src 'self'
  'nonce-…' 'strict-dynamic'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self';
  connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'`; plus
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy` (camera, microphone,
  geolocation off). `style-src 'unsafe-inline'` is an accepted risk (Recharts and Radix write inline style
  attributes); scripts stay nonce-only. Trusted Types: report-only first (F7 decides enforce or not).
- **Model text** (answers, deck bullets, notes, captions, alert text, upload verdict reasons) is rendered as plain text
  or through `@assistant-ui/react-markdown` (react-markdown, which ignores raw HTML by default) **plus
  `rehype-sanitize`**; `rehype-raw` is never added. Links: `http(s)` only, `rel="noopener noreferrer nofollow"`,
  shown with their host. **Images in model Markdown are not rendered** (an image URL is a classic exfiltration channel
  for injected instructions — the `img-src 'self'` CSP blocks it too). `dangerouslySetInnerHTML` is banned by an ESLint
  rule.
- Untrusted upload rows (`untrusted_upload`) and web / document evidence keep their trust label in the UI.

---

## 5. Run events in the browser (FastAPI plan §5)

- `EventSource` cannot send headers, and with the BFF it is not needed: the UI reads `GET /bff/runs/{id}/events` with
  `fetch` + `ReadableStream`, parsed by `eventsource-parser`. Each event's `data` is validated at runtime with the
  zod schema Orval generates from the F0 union (an unknown event or field → logged and ignored, never rendered).
- Reconnect: on a dropped stream, retry with `Last-Event-ID` (the API replays from the run's buffer); after the run's
  end, or if the buffer is gone, fall back to `GET /runs/{id}` (the final result).
- The BFF route handler streams the upstream body as it comes (no buffering, no compression), passes the 15 s
  heartbeat, and aborts upstream when the browser disconnects.
- What each event shows: `understood` → "understood as: …" line under the question (the standalone question, the
  entities used, `by: code / model`); `clarify` → the question back with its options as buttons (a click sends the
  chosen option as the next question); `queued` → position; `started` / `node` → a progress list of the graph's
  allow-listed node names (translated labels); `tool_called` → a chip per tool; `tool_refused` → a "not part of your
  access" chip with the refused part's text; `approval_needed` → the pack screen reloads; `answer` → the answer card;
  `done` / `failed` → final state (problem body: title + request id, never internals).

---

## 6.0 Product and design direction (owner 2026-11-06: "creativity — present the services smartly, simply, attractively")

Grounded in what the API and the graphs really return (knowledge graph refreshed 2026-11-06, then the code read:
`supervisor.answer_summary`, `deck/slots.Bound` / `Slot`, `RouteAdviceResult`, `VoyageWatchResult`, `deck/style.py`).
Each idea says what it needs; nothing here moves a decision into the browser.

1. **One home, the services as cards — "Today at the port" (`/[locale]`).** Only the products in `me.products`; each card
   = one live line + **one** primary action, composed from endpoints that exist (no new endpoint):
   - Weekly pack (Finance + CEO): `GET /packs` → "W45 waits for your decision · 2 Validator notes" → Review.
   - Voyage watch: `GET /voyage-watch/alerts?high=true` → "3 high alerts · last run 10:30" → Open.
   - Ask: the question box on the card itself + 3 starter questions per role (a fixed list in `messages/*.json`, shaped
     like the golden sets' questions — never generated).
   - Route advice: a two-field strip "origin → destination" → "Compare Suez and Cape".
   - Views (Finance + CEO): "Ask for a chart" → the views page.
2. **One question box everywhere** (`Ctrl+K`): plain text goes to the supervisor (its router decides); `/route` and
   `/chart` open those forms prefilled. A UX shortcut only.
3. **Every number has a receipt (the signature feature).** The project's core promise — every number bound to its
   evidence by code (slots, Validator) — made visible: numbers in answers, route reasons and watch items are chips;
   hover / tap → the field, the source view + filter, the evidence id. **Needs F0:** `answer_summary` returns `numbers:
   [{text, start, end, evidence_id, field, source}]` built from the state's `bound` (offsets in the rendered text);
   the same for `RouteAdviceResult.reasons` and `VoyageWatchResult.items` (rendered with slots too). This touches
   `pipelines/agents/graphs/supervisor.py` (+ route advice / watch summaries) — agreed with the approver session before
   F0 (D-FE-1). Until then: evidence chips per answer (exists today).
4. **Show the work, never the thoughts.** Progress as a short human stepper mapped from the allow-listed `node` /
   `tool_called` events ("Checking your access → Reading the finance views → Checking every number → Done"); a refused
   tool is a calm neutral chip "not part of your access", not an error.
5. **Calm by default, depth on demand.** A result card = headline + up to 3 key facts + one action; a "How we know"
   drawer holds evidence, sources, assumptions, problems, model calls. A partial answer shows the answered part first,
   the refused part in a quiet box.
6. **Pack review = slide review.** A filmstrip of the 10 slides (HTML replicas from the draft + `charts_drawn`), the
   current slide large, the change panel beside it; Validator problems pinned to their bullet; after a re-validation a
   "what changed" view (old / new text, chart choice); the status badge styled like the deck's own ("Draft for
   approval" amber `#EDA100` → "Approved" green `#1BAF7A`). The PPTX stays the source of truth (download).
7. **Route advice = a decision, not a report.** Suez | Cape as two cards side by side (distance, days, fuel, toll,
   total, risks) from `comparison`; the recommended one carries the badge and the difference row reads "saves X SDR ·
   +Y days"; a simple SVG strip "origin → Suez / Cape → destination" instead of a map (F9).
8. **Voyage watch = a radar list.** Vessels by severity; per row an ETA drift bar (rule ETA vs schedule, from `etas`)
   and alert chips; filter chips high / all; the next run time.
9. **One visual identity with the deck and Power BI** (`deck/style.py`): navy `#0B2545`, Nile teal `#13A89E`, ink /
   greys, series colours billed `#2A78D6`, budget `#A3A29C` dashed, week marker `#EB6834` — validated for the web with
   the dataviz skill (contrast in light **and** dark themes); a single thin teal "Nile line" motif in the header and
   empty states, no stock maritime clip-art; Arabic-first typography (an OFL pair, §8); motion small and purposeful,
   `prefers-reduced-motion` respected.
10. **Empty states that teach:** every page offers 3 starter actions for the asker's role.
11. **Simplicity guard:** one primary action per card / screen; no dashboard of dashboards; each page reviewed by the
    owner on ar + en screenshots ("can I tell what to do in five seconds?").

**Concept gate (F1, before any page is built):** the Frontend Design skill sets the direction, UI UX Pro Max writes the
tokens into `MASTER.md`, then a clickable static concept of three screens — home, an answer card with number receipts,
the pack slide review — in Arabic and English. **The owner approves the look before F2** (D-FE-3).

## 6. Pages

Each page: route, endpoints, what it shows, what the API decides. Buttons hidden by `/me` are a comfort only.

### 6.1 Login (`/[locale]/login`)
Email + password → `POST /bff/login`. One message for every 401 ("email or password is wrong" — the API gives the same
401 for both, ADR-064); 429 / lockout → "try again in N minutes" from `Retry-After`. No "remember me", no sign-up, no
password reset (the owner creates logins with `Api_admin.py`). Language switch on the page.

### 6.2 Shell
Header: the employee (name from `/me` if F0 adds it, else id), role, department; the products menu built from
`me.products`; status badge from `/health/ready` (green / degraded, counts only); language switch (keeps the path);
logout. 404 page for "not found or not yours" (the API's IDOR rule: never "exists but hidden").

### 6.3 Chat over the supervisor (`/[locale]/chat`, `/chat/[conversationId]`)
- **assistant-ui (MIT) on a custom runtime** (`ExternalStoreRuntime`) over our endpoints — not
  `@assistant-ui/react-langgraph`, not CopilotKit (ADR-060 amendment 1 (a)). Thread list = `GET /conversations`;
  new = `POST /conversations`; close = `DELETE` (memory turns deleted, ADR-065 (5)).
- Send: `POST /conversations/{id}/questions {question ≤ 2,000, lang: null}` (the API detects the language; an English
  question in the Arabic UI is answered in English) → 202 → the event stream (§5).
- **The answer card:** status badge (answered / **partial** — the refused part shown in its own box / not_permitted /
  not_in_data / validation_failed / output_invalid, each with a plain sentence), the rendered answer (sanitized
  Markdown, `dir="auto"`), evidence chips (tool + source, ids), model calls (fresh / cached), the thread id; the
  **LangSmith link only when the API sends it** (owner only, decided by the API).
- **Uploads:** drop zone (PDF / DOCX ≤ 5 MB, checked client-side for comfort) → `POST …/uploads` → the verdict card
  (accepted / refused, removed sections with reasons, `document_code`, chunks); the list with delete; "request
  promotion" only for a manager of the same department (`/me`), the API decides (ADR-044). Upload text is never shown
  back (the API returns no text).
- History page (`/history`): `GET /questions` → `GET /questions/{thread}` (the asker; the CEO sees all).

### 6.4 Weekly-pack approval (`/[locale]/packs`, `/packs/[thread]`, `/packs/report`)
Finance (any role) + CEO see it (others get 404 from the API → the menu item is hidden by `/me`).
- **List:** week, attempt, status, waiting / ended, degraded (`GET /packs`).
- **Detail (`GET /packs/{thread}`):** readiness reasons, Validator problems, the degraded note, the draft **slide by
  slide** (bullets with their index, the approver's additions marked "Approver's addition"), the Insight notes with
  their origin (PLANNED approver E), the current chart choices + a Recharts preview of `trend` / `variance` from
  `charts_drawn` (PROPOSED F0; the PPTX stays the source of truth), the approval log, `redrafted: true` banner
  ("earlier edits and additions were not carried — re-add what you still want", approver plan D2), downloads:
  preview PPTX / published deck.
- **The decision panel** (Finance manager or CEO; the API and the graph check again):
  | Kind | UI | Rules mirrored client-side (the server stays authoritative) |
  |---|---|---|
  | `approve` | one button + optional comment (≤ 500) | carries no changes |
  | `edit` | inline text edit per bullet (`edits`), "add a bullet" on allowed slides (`additions`, ≤ 300 chars, ≤ 2 per slide, slides from `allowed`), chart options from the catalogue (`charts`, ≤ 3, one per chart) | at least one change; no analysis edits or steer (D1) |
  | `revise` | the notes editor (`analysis_edits`: summary replace; driver explanation replace; context / caveat replace / remove / add, ops from the catalogue / `ANALYSIS_OPS`, ≤ 10, ≤ 400 chars each, evidence ids picked from the evidence list) and / or a steer box (≤ 300); chart changes allowed | no text edits or additions (D1); "revises left: n of 2" (D3) |
  | `reject` | button + required comment | carries no changes |
  Submit → 202 → run events (`insight_*` / `writer` / `validator` nodes for a `revise`) → `approval_needed` → the detail
  reloads; a `refused` result shows its reasons next to the field it names; 409 → "someone else is deciding this pack /
  it is no longer waiting".
- **Report (`/packs/report`):** G5 edit rate + counts per kind (D4) (PLANNED approver E).

### 6.5 Views / charts (`/[locale]/views`)
- Two inputs, one result: **a question** (≤ 300 chars → `POST /views {question}` → 202 → SSE; `done` carries the
  `ViewSpec` **or** an ask-back with options — approver plan D5) or **a choice form** built from `GET /charts/catalogue`
  (kind `trend` / `category` / `aging` / `customers`, week, series ≤ 3 of one unit, window 4 / 8 / 13 / 26, measure,
  rows, compare week → `POST /views {choice}` → 200 `ViewSpec`).
- **Drawing (Recharts):** `trend` → line chart (categories = weeks); `category` / `customers` → bar chart (two series
  when `compare_week`); `aging` → bar chart of the buckets. One unit per chart (`SDR` / `%` / `days`) on the axis;
  `null` values = gaps, never zero; the **caption is the API's (code-written)**; sources listed under the chart; a
  table view of the same numbers (accessibility, and what Playwright compares). No client-side arithmetic on values
  (formatting only).
- `not_permitted` → the problem body's message, no chart (RBAC in the tool, approver plan §2d).

### 6.6 Route advice (`/[locale]/route-advice`, `/route-advice/[thread]`)
Form = `RouteIn`: a vessel id **or** vessel type + condition (Laden / Ballast) + SCNT tons; origin and destination as
5-character UN/LOCODE (validated by pattern; a port picker list is out of scope); speed 4–25 kn optional → 202 → SSE →
result: status, comparison table (one row per route option), the recommendation, headline / reasons / risks
(rendered text), assumptions, sources, problems. List of past advice (`GET /route-advice`).

### 6.7 Voyage watch (`/[locale]/voyage-watch`, `/voyage-watch/runs/[thread]`)
Alerts (any employee, level 1): `GET /voyage-watch/alerts?thread&vessel&high` — table with severity, vessel, rule,
ETA, text; filters in the URL. Runs (Operations + CEO): the list and one run's result (fleet counts, ETAs, alerts,
brief, headline / items, sources). Read-only (Task Scheduler starts runs).

### 6.8 Run graph view (React Flow) — small, last
For a pack decision run only: the `weekly_pack` graph's allow-listed nodes as a static React Flow diagram with the
`node` events lighting the current step (ADR-060 amendment 1 (c)). Elsewhere a plain progress list is enough.

### 6.9 Finance dashboard — the Power BI pages, shown smart in the web (`/finance`) — **D-FE-7, APPROVED (owner 2026-11-06)**

Owner, 2026-11-06 (relayed by the approver-plan session, chosen as a clickable option "In the frontend
(recommended)"): the Power BI finance dashboard must be shown smartly in the web UI, not only the weekly pack. Free
(Power BI Embedded needs a paid capacity and "publish to web" is public — ROADMAP Frontend row). **Approved by the
owner 2026-11-06 ("موافق على D-FE-7"); built in F0b + F5b.**

- **Same numbers everywhere:** every value is a row of the `finance` views (migration 013 and later), the same rows
  Power BI reads by DirectQuery and the pack's slots bind. No KPI math in the API or the browser (ADR-047,
  `docs/finance_metrics.md`); the browser only lays out, formats and draws.
- **Pages** (mirror the Power BI report `powerbi/PortPilot_Finance.Report`): **Overview** (KPI cards with WoW, the
  billing / budget chart), **Revenue** (billing by category, the trend), **Receivables** (AR, ageing, the overdue
  list), **Customers** (13-week customer view), **Exceptions** (the invoice audit findings), **Executive** (the
  short CEO view). **Owner update 2026-11-12:** remove the duplicate Smart View tab; the same catalogue/question
  flow stays on **Charts** (`/views`, §6.5, ADR-066). Old `/finance?page=smart` bookmarks fall back to Overview.
  One week picker for all pages (default: the latest closed week).
- **Smart, not a copy of Power BI:** each page opens with a two-line summary built from the rows (which number moved,
  which bucket grew) by fixed code rules, every number a receipt chip (§6.0 (3)); "Ask about this page" pre-fills the
  question box with the page and week; the charts use the deck / Power BI colours (MASTER §2) and the dataviz rules.
- **RBAC:** the API decides, exactly as for the agents' tools (finance department + CEO; others get the API's
  refusal and the page shows "Not part of your access"); the menu entry only appears when `/me` lists the product.
- **API addition (F0b, `pipelines/api/` only, reusing code, no new SQL):**
  - `GET /api/v1/finance/weeks` → the report weeks available (from `finance.dim_week`, through the same read path).
  - `GET /api/v1/finance/{dataset}?week=YYYY-Www` with `dataset` ∈ `weekly | category | customers | overdue | trend`
    → calls `pipelines/agents/tools/finance.finance_kpi(user, dataset=…, report_week=…)` and returns its rows and
    `source` unchanged in a typed response model (`FinanceRows`); its RBAC refusal → 403 problem body.
  - `GET /api/v1/finance/invoice-audit?week=YYYY-Www` → `pipelines/agents/tools/audit.invoice_audit(user, …)`,
    same pattern (`AuditRows`).
  - No LLM, no run, no SSE: plain reads, rate-limited like the other reads, logged in `api.audit_log`; the OpenAPI
    snapshot regenerated and the BFF allow-list regenerated from it (`npm run gen:allowlist`).
  - Per dataset rather than per page: one RBAC path per tool, pages composed in the UI from 1–3 calls, nothing in
    the API that knows Power BI's layout. Whether the Executive page's YTD figures come from `weekly`'s YTD columns
    (migration 022) is checked in F0b before the endpoint list is final (**uncertain**).
- **Not in scope:** Power BI Embedded / iframes, editing the Power BI model, new KPIs (a missing figure becomes a
  view change through its own migration and plan).
- **Checks:** a contract test per endpoint in `Api_check.py` (rows equal the tool's rows for 2 weeks; an employee
  outside finance → 403); Playwright per page (desktop + mobile, axe, no sideways scroll); a hand-check of one week's
  Overview numbers against Power BI Desktop by the owner.

---

## 7. The generated client

- **Orval 8.44.0** reads `docs/api/openapi.json` (the committed snapshot, ADR-064 P7 — `tools/openapi_snapshot.py`)
  → `web/src/api/generated/`: TanStack Query hooks + zod schemas (for runtime checks of SSE event data). Base URL =
  `/bff`. The generated folder is committed; the CI regenerates it and fails on a diff (the contract cannot drift).
- **F0 makes it worth it** (owner F2): response models for every untyped response of §2, `RunEvent` as a
  discriminated union on `event` (one model per event of the FastAPI plan §5), the bearer `securitySchemes`, `UploadOut`
  wired as the upload response, the planned approver endpoints typed from the start (`ApprovalDecision` without
  `approver_employee_id`, `ViewChoice`, `ViewSpec`, the catalogue).
- The SSE reader (§5) is hand-written (Orval does not generate streams) but its types come from the generated union.

---

## 8. Arabic RTL + English

- `next-intl` 4.14.9 with `[locale]` routes; `<html lang dir>` set per locale; messages in `web/messages/ar.json` /
  `en.json` (UI strings only — model text comes from the API in the language of the question).
- **Layout:** Tailwind logical utilities only (`ms-/me-/ps-/pe-`, `start-/end-`, `text-start`); an ESLint rule (or a
  grep in CI) bans physical `ml-/mr-/pl-/pr-/left-/right-` in `web/src`; icons that point (arrows, chevrons) mirrored
  in RTL.
- **Mixed direction:** model text blocks `dir="auto"`; codes and ids (UN/LOCODE, thread ids, vessel ids, evidence ids,
  amounts with SDR) in `<bdi>` so they never flip; tables right-aligned in Arabic with numeric columns aligned by digits.
- **Numbers:** Latin digits in both locales (F6), formatted with `Intl.NumberFormat` (`ar-EG-u-nu-latn` / `en`);
  values from the API are never re-rounded beyond display formatting.
- **Charts:** the time axis runs left → right in both locales (weeks read as on the deck and Power BI); labels,
  legends and tooltips translated and placed on the start side in RTL.
- **Fonts:** a free OFL Arabic + Latin pair (candidates: IBM Plex Sans Arabic + IBM Plex Sans, or Noto Sans Arabic +
  Noto Sans), self-hosted through `next/font` at build time (no font request to a third party at run time; CSP
  `font-src 'self'`). Picked in F1 with the design system.
- **Checked:** every Playwright page test runs in both locales; a visual check of RTL mirroring per page (screenshots
  in the plan's progress notes).

---

## 9. Packages (pinned exactly; free / open source)

Versions checked 2026-11-06 with `npm view <pkg> time`: the highest release published **on or before 2026-10-23**
(the two-week rule). F1 installs with `npm install --save-exact --before=<14 days ago>` and re-checks; `.npmrc`:
`save-exact=true`, `engine-strict=true`; Node 24 (installed: 24.20.0, npm 11.19.0).

| Package | Version (date) | Licence | Role |
|---|---|---|---|
| `next` / `eslint-config-next` | 16.4.2 (2026-10-15) | MIT | framework / lint rules |
| `react`, `react-dom` | 19.3.1 (2026-10-14) | MIT | — |
| `typescript` | **6.0.3** (2026-04-16) | Apache-2.0 | 7.0.2 is newer but `typescript-eslint` 8.72.0 requires `<6.1.0` |
| `typescript-eslint` | 8.72.0 (2026-10-19) | MIT | — |
| `eslint` | 10.13.0 (2026-10-16) | MIT | — |
| `prettier` | 3.9.10 (2026-10-10) | MIT | — |
| `@types/react`, `@types/react-dom` | 19.3.0 (2026-09-09) | MIT | — |
| `@types/node` | 24.19.2 (picked at F1) | MIT | matches Node 24 |
| `clsx`, `tailwind-merge`, `class-variance-authority`, `radix-ui`, `tw-animate-css` | 2.1.1, 3.7.0, 0.7.1, 1.8.1, 1.4.0 (F1) | MIT | the shadcn/ui helpers + Radix primitives |
| `server-only` | 0.0.1 (F1) | MIT | keeps the BFF code out of client bundles |
| `tailwindcss`, `@tailwindcss/postcss` | 4.3.3 (2026-07-16) | MIT | styling |
| `shadcn` (CLI, dev) | 4.22.1 (2026-10-18) | MIT | copies components into `web/src/components/ui/`; the Radix packages they pull are pinned at install |
| `lucide-react` | 1.61.0 (2026-10-21) | ISC | icons |
| `@assistant-ui/react` | 0.15.31 (2026-10-22) | MIT | chat UI (0.x: minors may break → exact pin, Dependabot PRs reviewed by hand) |
| `@assistant-ui/react-markdown` | 0.14.24 (2026-10-22) | MIT | Markdown (react-markdown 10.1.0) |
| `rehype-sanitize` | 6.0.0 | MIT | sanitizer |
| `@tanstack/react-query` | 5.104.5 (2026-10-19) | MIT | server state |
| `orval` (dev) | 8.44.0 (2026-10-21) | MIT | client generator (needs Node ≥ 22.18) |
| `zod` | 4.6.7 (2026-10-12) | MIT | runtime checks of events |
| `eventsource-parser` | 4.1.2 (2026-10-12) | MIT | SSE over `fetch` (chosen over `@microsoft/fetch-event-source` 2.0.1, unchanged since 2021) |
| `recharts` | 3.10.1 (2026-07-25) | MIT | charts (owner F3) |
| `@xyflow/react` | 12.12.0 (2026-09-24) | MIT | run graph view (§6.8) |
| `next-intl` | 4.14.9 (2026-10-02) | MIT | i18n / RTL |
| `@playwright/test` (dev) | 1.64.1 (2026-10-14) | Apache-2.0 | E2E + logic tests |
| `@axe-core/playwright` (dev) | 4.14.0 (2026-10-15) | MPL-2.0 | accessibility checks |

Paid upgrade paths (noted, not used): Playwright on a hosted grid, Sentry paid tiers, a commercial map tile service.

The Claude Code tools and skills are §9a.

---

## 9a. Claude Code tools and skills — one job each, no overlap (owner reminder 2026-11-06)

Everything agreed earlier (ADR-060 amendments 1–2, the third-party review rule, the owner's "no superpowers"
decision of 2026-10-31) in one place, each with **one job**, so two tools never decide the same thing.

**Order of precedence when two sources disagree:** (1) the project's rules — `CLAUDE.md`, the ADRs, this plan
(security §4, RTL §8, packages §9); (2) the design system `web/design/MASTER.md` once the owner approves it in F1;
(3) the docs of the **pinned** version (Context7); (4) a skill's general advice (Vercel, UI UX Pro Max, Frontend
Design). A lower source never overrides a higher one; a real conflict is written in Progress / deviations and asked.

**Review before install** (F1, like the langchain-skills; recorded in `.claude/skills/README_third_party.md` with
source, licence, version / commit, file hashes, network calls, what it installs; never run a repository's installer
script): every item marked "review" below.

| Layer | Tool / skill | Its one job | Not used for (handled by) | Status |
|---|---|---|---|---|
| Design | **Frontend Design** skill (Anthropic plugin) | the aesthetic direction once, in F1: tone, type scale, layout identity, what makes NileGate's UI not a template | tokens and palettes (UI UX Pro Max → `MASTER.md`); charts (dataviz) | enabled (owner plugin 2026-10-30) |
| Design | **UI UX Pro Max** (MIT open-source edition, copied at a pinned commit into `.claude/skills/`; not the paid tier, not the `uipro-cli` installer) | fills the direction with concrete tokens — palette, font pairing candidates, spacing, component states, UX / accessibility rules — written **once** to `web/design/MASTER.md`; later searches only read it | the direction (Frontend Design); Arabic fonts and RTL rules (ours, §8); chart colours (dataviz) | review: its Python search scripts stdlib-only, no network, nothing installed |
| Design | **dataviz** skill (already used for the deck, ADR-051 / ADR-061) | chart colours, marks, legends, tooltips for Recharts — validated with its colour checker and matched to the deck's palette (`deck/style.py`: navy / teal, billed blue, budget grey) so web = deck = Power BI | page design (MASTER.md); which chart variant (the API's catalogue) | available |
| Code | **Vercel React skills** (best practices, composition patterns; copied at a pinned commit) | React / Next.js code patterns: server vs client components, data fetching, composition, re-render cost | library API details (Context7); security choices (this plan §4 wins, e.g. no `dangerouslySetInnerHTML`, BFF cookie) | review |
| Code | **shadcn MCP** (`shadcn@4.22.1 mcp`, pinned in `.mcp.json`) | find and add shadcn/ui components from the **official registry only**; they are copied into `web/src/components/ui/` and owned by us | other registries (not added without a review); styling decisions (MASTER.md) | review |
| Code | **Context7 MCP** (`@upstash/context7-mcp@4.4.4`, 2026-10-19, MIT, pinned in `.mcp.json`) | current docs **for the pinned version** of a library (Next 16.4, Recharts 3.10, assistant-ui 0.15, next-intl 4.14, Orval 8.44 …) | patterns (Vercel skills); its pages are untrusted data (project rule 5); queries carry library names only, never project data or code | review: what it sends to Upstash, whether a key is needed (free tier) |
| Code | **PostToolUse hook** on `.ts` / `.tsx` in `web/` | runs the project's own `web/node_modules/.bin/prettier --write` and `eslint` (report only, no `--fix`) after each edit, so formatting never needs a manual step | the gate (the CI is the gate); no `npx` download, no git, beside the existing PreToolUse guard hook (different event, no clash) | new in F1 |
| Loop | **`frontend-dev-loop`** skill (ours, F1) | the order of work and which tool when (§10): edit → lint / tsc → built-in browser → Playwright spec in `ar` + `en` → DevTools MCP only when needed → handoff | Python (`script-dev-loop` stays the pipelines' loop) | new in F1 |
| Loop | `script-dev-loop` (ours) | F0's backend checks (`Api_check.py` style ✅ lines) | `web/` | existing |
| Verify | **Built-in browser** (`Claude_Browser`, `preview_start` from `.claude/launch.json`) | day-to-day: open the dev server, `read_page`, console, network list, screenshots as proof | performance traces, deep network detail (DevTools MCP); repeatable proof (Playwright) | existing |
| Verify | **Chrome DevTools MCP** (`chrome-devtools-mcp@1.11.0`, isolated profile, headers redacted) | only what the built-in browser lacks: performance traces, Lighthouse, request / response detail, network / CPU emulation, memory snapshots | normal clicking and reading (built-in browser) | existing (ADR-060 amendment 2) |
| Verify | **`@playwright/test`** | the repeatable proof: E2E, logic tests, axe, RTL snapshots, CI | exploring a page (built-in browser) | §9 package |
| Review | built-in **`security-review`** and **`code-review`** skills | one review of the whole `web/` diff + F0 at F7, before the owner's commit | — (they complement the CI, they do not replace it) | available |
| Map | **graphify** | where something is decided / implemented (code ↔ ADR ↔ plan); `.graphifyignore` gains `web/node_modules/`, `web/.next/`, `web/src/api/generated/`; `/graphify . --update` after the docs of F7 | reading many files blindly | existing |
| Ops | Sentry MCP (owner's claude.ai connector) | backend errors only (ADR-062) | the browser (F10: frontend Sentry deferred) | existing |

**Not used, on purpose:** the Playwright MCP and frontend subagents (ADR-060 amendment 1: the built-in browser +
`@playwright/test` + the `frontend-dev-loop` skill instead); the **superpowers** plugin (owner 2026-10-31 — its own
plans, pytest TDD, worktrees and commits per task clash with `CLAUDE.md`; owner decisions are asked as clickable
choices instead of its brainstorming); Claude in Chrome for the app (it is the owner's real Chrome with his sign-ins;
used only if he asks); the Data plugin's `build-dashboard` (CDN scripts break the CSP) and `data-visualization`'s
Python chart code (the web draws with Recharts); the langchain-skills (no graph code in this plan); the Power BI
Modeling MCP (Power BI stays Desktop and is not touched here).

---

## 10. Testing

Project style: proof by scripts with ✅ lines; here the runner is `@playwright/test` (F8), wrapped so `tools/run.py`
style output exists: `npm run check` prints one ✅ line per suite.

1. **Static:** `tsc --noEmit`, ESLint (incl. the bans: `dangerouslySetInnerHTML`, physical direction classes, `any`
   in `src/api`), Prettier check, Orval regenerate → no diff.
2. **Logic tests** (Playwright runner, no browser): the SSE parser (split chunks, heartbeats, reconnect with
   `Last-Event-ID`, an unknown event ignored); the D1 / D3 client rules = `ApprovalDecision`'s server rules on the same
   cases (cases exported from the API's models in F0 as a JSON fixture, so the two sides cannot drift); `ViewSpec` →
   Recharts props (units, gaps, compare series).
3. **E2E, mocked API (CI, database-free like ADR-063):** the BFF points at a tiny fixture server whose responses are
   generated from the F0 models (+ recorded event streams); every page in `ar` and `en`; axe on every page (0 serious /
   critical); RTL screenshot comparisons per page (Playwright snapshots, committed).
4. **E2E, local stack (owner's machine):** the real API started in a **test mode** (PROPOSED F0: `Serve.py
   --fake-roles`, refused unless bound to the loopback and `API_FAKE_ROLES=1`) with `FakeRoles` (no LLM quota) over the
   real databases; test logins from `.env` (`WEB_E2E_*`, git-ignored; created with `Api_admin.py`). Covers: login /
   logout / lockout message; the access matrix (employee / manager / CEO × Finance / Operations / HR) — every page and
   action gives the API's answer, **leakage 0** (no other employee's thread, pack or upload visible); chat with a
   partial answer and a refused tool; a follow-up → `understood`; a clarify → options; an upload → verdict → an answer
   citing `untrusted_upload`; a pack on a test thread: `edit` (text + addition + chart) → re-validated → approve →
   deck download; `revise` → `redrafted` banner; a second decision at once → 409 shown; views: a choice and a question
   → the drawn SVG values equal the `ViewSpec` (read from the DOM); route advice; watch alerts.
5. **Security E2E:** answers carrying the injection set's payloads (`Data/processed/agents/eval/injection_golden.jsonl`
   shapes: `<script>`, `<img src=…>`, `javascript:` links, Markdown images) render inert — no script runs, no request
   leaves the origin (Playwright network log), no image from model text; `document.cookie` lacks `ng_session`,
   `localStorage` / `sessionStorage` hold no token; a cross-origin POST to `/bff/*` → 403; a path outside the
   allow-list → 404; the CSP and security headers present on every page.
6. **One real-model smoke** (owner, at the end): one EN and one Egyptian Arabic question, one follow-up, one view
   question, one route advice, and the real pack of a Monday decided through the UI.
7. **Performance (light):** a Lighthouse / trace pass with the Chrome DevTools MCP on chat and packs (no budget gate;
   findings recorded).

**`frontend-dev-loop` skill** (`.claude/skills/frontend-dev-loop/SKILL.md`, written in F1, like `script-dev-loop`):
edit → `npm run lint && npm run typecheck` → the dev server through `.claude/launch.json` + the built-in browser
(`read_page` / console / network, never whole DOM dumps) → the page's Playwright spec in both locales → screenshot proof
→ the Chrome DevTools MCP only for traces / network detail → a handoff line in this plan. Token discipline: no reading
of `node_modules`, `.next`, lock files or generated code beyond a grep.

---

## 11. CI, Compose, phases

### 11.1 CI (`.github/workflows/ci.yml`, a new `web` job beside the Python one)
`actions/setup-node` (pinned major, Node 24) with the npm cache → `npm ci` in `web/` → Orval no-diff → `tsc` →
ESLint → Prettier check → `next build` → Playwright (mocked API, Chromium) → upload the report on failure;
`npm audit --omit=dev --audit-level=high` (the `pip-audit` of npm); `NEXT_TELEMETRY_DISABLED=1`. Dependabot: an `npm`
entry for `/web` (weekly, grouped minor / patch; 0.x packages one by one). The API's OpenAPI snapshot diff (ADR-064 P7)
stays.

### 11.2 Docker Compose (F7, plan default F7)
`compose.yaml` at the root with one service `web`: a multi-stage `web/Dockerfile` (Node 24 slim, `npm ci`, `next build`,
the standalone output, a non-root user), published on `127.0.0.1:3000` only; `NILEGATE_API_URL` points at the API on
the host. **Uncertain:** whether a container reaches a host service bound to `127.0.0.1` on Docker Desktop for Windows
(`host.docker.internal`) — F7 tests it first; fallback: the API also binds the Docker host gateway address (an ADR-064
note), or the web runs on the host with `next start`. The three databases keep their existing containers and
scripts; the API in Compose stays the ROADMAP's "Docker Compose for all services" row (trigger: the API no longer
shares files with host CLIs).

### 11.3 Phases

| Phase | Content | Depends on |
|---|---|---|
| **F0** | **API contract pass** (`pipelines/api/` only, + `tools/openapi_snapshot.py` run): response models for every untyped response; `RunEvent` discriminated union; bearer `securitySchemes`; `UploadOut` wired; `GET /packs/{thread}` + `allowed` + `charts_drawn`; the approval rule cases as a JSON fixture; `Serve.py --fake-roles` test mode; the number receipts of §6.0 (3)
(`numbers` spans in the answer / route / watch summaries — touches `pipelines/agents/graphs/`, agreed first, D-FE-1); OpenAPI snapshot regenerated; `Api_check.py` 10 / 10 unchanged + a contract phase (every response validates against its model). | the approver plan's Phase E–F **done** (same files: `routers/packs.py`, `schemas.py`) — or the approver session types its new endpoints itself (to be agreed) |
| F1 | Scaffold + tooling: `web/` (Next.js, TS, Tailwind, shadcn init, next-intl ar / en, ESLint / Prettier, Orval config, the BFF skeleton with the allow-list, CSRF and CSP), `.npmrc`, the Claude tooling of §9a reviewed then installed (records in `README_third_party.md`), `frontend-dev-loop` skill, design system (`MASTER.md`, fonts, RTL rules) with the Frontend Design skill + UI UX Pro Max, **the concept gate of §6.0 (three screens, ar + en, approved by the owner before F2)**, the CI `web` job, Dependabot npm, `.claude/launch.json` entry | F0 (for Orval) |
| F2 | Login, shell, `/me`, health badge, logout, 404; auth + CSRF + header E2E | F1 |
| F3 | Chat: conversations, assistant-ui runtime over SSE, answer card (partial / refused / evidence), `understood` / `clarify`, uploads + promotion, history | F2 |
| F4 | Weekly pack: list, detail, downloads, the decision panel (all kinds), run progress, `redrafted`, refusals, report; **D-FE-9:** the "Write your request" box → proposal (`understood`, steps) → Confirm (409 `stale` handled) | F2 + approver Phase E |
| F5 | Views page + the pack's chart preview (Recharts), catalogue form, question with ask-back | F2 + approver Phase F |
| **F5b** (D-FE-7, approved 2026-11-06; navigation simplified by owner 2026-11-12) | Finance dashboard `/finance`: F0b endpoints (`/finance/weeks`, `/finance/{dataset}`, `/finance/invoice-audit`) + the six pages, summaries by code rules, receipts, week picker; custom charts stay on `/views`; **D-FE-9:** the "This week's pack" panel (`GET /finance/pack`) | F5; F0b in `pipelines/api/` after the approver plan's API work (same files) |
| F6 | Route advice, voyage watch (alerts + runs), the React Flow run view for pack runs | F2 |
| F7 | Compose `web` service, security E2E complete, axe 0 serious, DevTools performance pass, the real-model smoke, docs: ADR-060 amendment 3 (BFF cookie auth, Recharts, the F0 contract, Compose scope), ARCHITECTURE §2 / §7 / §8, `docs/THREAT_MODEL.md` web-UI table (XSS, CSRF, token theft, open proxy, clickjacking, exfiltration through images / links, dependency supply chain), ROADMAP, plan archived, `/graphify . --update`; the owner commits once (F4) | F3–F6 |

F3 and F6 can run in parallel after F2 (different routes, no shared files beyond the shell).

---

## 12. Done when

- (D-FE-7) the six finance pages and the separate Charts page in the web show, for a hand-checked week, the same
  numbers as Power BI Desktop and the pack; RBAC refusals come from the API.
- The concept of §6.0 approved by the owner (F1); the home page shows only the asker's services, each with one live
  line and one action; number receipts on answers, route reasons and watch items (or, if D-FE-1 is not agreed, the
  per-answer evidence chips, recorded).
- Every page of §6 works against the API in both locales; every endpoint marked EXISTS or PLANNED in §2 is used by a
  screen (PLANNED ones once the approver plan has shipped them).
- F0 merged: no untyped response in `docs/api/openapi.json` (except file downloads), the event union typed,
  `Api_check.py` 10 / 10 + its contract phase ✅, the no-regression checks of the FastAPI plan unchanged.
- `npm run check` ✅: `tsc`, ESLint, Prettier, Orval no-diff, logic tests, mocked E2E in `ar` + `en`, axe 0
  serious / critical; the CI `web` job green; `npm audit` high = 0.
- Local-stack E2E ✅ with **leakage 0** across the access matrix; the security E2E ✅ (inert payloads, no token in JS,
  CSRF / allow-list refusals, CSP present); the drawn chart values = the `ViewSpec` values.
- The owner, on a real Monday pack, decides it through the UI (including at least one approver change), and asks one
  EN + one Egyptian Arabic question with a follow-up.
- `docker compose up web` serves the app on `127.0.0.1:3000` (or the recorded fallback).
- ADR-060 amendment 3 written; ARCHITECTURE, THREAT_MODEL and ROADMAP updated; the plan archived with its
  implementation record; one commit by the owner.

---

## 13. Risks and open points

| Risk | Mitigation |
|---|---|
| F0 and the approver plan edit the same API files | F0 starts only after approver Phase F, or the approver session types its own new endpoints (agree before F0) |
| `@assistant-ui/react` is 0.x (breaking minors) | exact pin, the runtime adapter isolated in one file, Dependabot PRs reviewed by hand |
| SSE through the BFF buffered by a proxy layer | explicit streaming response, no compression; a logic test with chunked fixtures; a local-stack E2E watching events arrive before `done` |
| The first real pack decision (2026-11-09) happens before F4 | the CLI / API path stays; the UI is not on the critical path of any Monday |
| Docker Desktop reaching a loopback-bound host API | F7 spike first; fallbacks recorded in §11.2 |
| Model text in Arabic + English mixed in one block | `dir="auto"` + `<bdi>`; RTL screenshots reviewed by the owner |
| `style-src 'unsafe-inline'` | scripts stay nonce-only; revisit if Recharts / Radix allow nonce-styled attributes |
| Recharts in RTL (axis / legend mirroring) | the LTR time-axis rule (§8); the snapshots show both locales |

---

## Progress / deviations

- 2026-11-10 stabilization (approved `Project_validation_and_continuation_plan.md`, R4/R7): direct decisions
  send the displayed review version; background refresh clears obsolete form inputs. OpenAPI/client regenerated.
  Stream reconnects use backoff and event-ID deduplication; failed streams fall back to bounded polling until a
  terminal event, with cancellation and transient-error recovery. Added transport logic tests and a stale-tab
  approval browser test. The original live-model/owner acceptance gates below remain open.

- 2026-11-06 — written (PROPOSED) in a side session at the owner's request, in parallel with the approver plan; owner
  decisions F1–F4 asked once as clickable choices, all answered as recommended; defaults F5–F10 set by the plan, open
  to change at approval. Package versions checked with `npm view` (cut-off 2026-10-23). Nothing installed, no code.
- 2026-11-06 — owner reminder during the writing ("don't forget the tools and skills we discussed, with no conflict
  between them") → §9a added: each tool / skill with one job, an order of precedence, the review-before-install list,
  and what is not used on purpose.
- 2026-11-06 — **APPROVED** by the owner ("موافق"), with one condition first: refresh the knowledge graph so no
  decision is taken blind. `/graphify . --update` done: 133 changed files (118 code by AST, 15 docs by 4 extraction
  agents; one agent's first read of `decisions.md` stopped at line 1520 and was sent back to read ADR-064 / ADR-065;
  ADR nodes of `ARCHITECTURE.md` / `pipelines/README.md` re-pointed to the canonical `docs_decisions_adr_NNN` ids, no
  duplicates) → **4,415 nodes, 10,232 edges, 255 communities**; 197 replaced nodes all came from the re-extracted
  files (checked before writing); health: 6 self-loop edges, nothing dangling. Owner then asked for creativity and a
  smart, simple, attractive presentation of the services (owner asleep; decisions taken as recommended, for review):
  - **D-FE-1 — number receipts need one field from the graphs:** `supervisor.answer_summary` returns the rendered
    answer and per-answer evidence, not where each number is; the state's `bound` (`Slot.eid`, `field`, `start`,
    `end`) holds it. F0 adds `numbers` spans to the answer / route / watch summaries — a change in
    `pipelines/agents/graphs/`, so it is agreed with the approver session before F0; fallback = per-answer chips.
  - **D-FE-2 — the home page needs no new endpoint:** composed from `/me`, `/packs`, `/voyage-watch/alerts`,
    `/questions`, `/route-advice`.
  - **D-FE-3 — a concept gate in F1:** three static screens (home, answer card with receipts, pack slide review) in
    ar + en approved by the owner before F2.
  - §6.0 added (eleven design principles, the deck's palette from `deck/style.py` as the shared identity).
- 2026-11-06 — **F1 done (owner: "ابدأ F1"); the concept gate waits for the owner.** Handoff:
  - **Tools of §9a** reviewed then installed, recorded in `.claude/skills/README_third_party.md` (pinned commits, zip
    hashes, review notes): UI UX Pro Max (MIT edition, stdlib scripts, no network), Vercel React best practices +
    composition patterns, shadcn MCP `4.22.1` and Context7 MCP `4.4.4` in `.mcp.json` (Context7 sends library name +
    query only, OpenTelemetry off). The owner approves the two new project MCP servers on Claude Code's next start.
    The PostToolUse hook `.claude/hooks/web_format.py` (Prettier write + ESLint report, exit 2 on problems; tested on
    a planted `ml-2`) and the `frontend-dev-loop` skill are in place.
  - **`web/`**: packages of §9 installed with `npm_config_before=2026-10-23` and exact pins, plus the shadcn helpers
    `clsx 2.1.1`, `tailwind-merge 3.7.0`, `class-variance-authority 0.7.1`, `radix-ui 1.8.1`, `tw-animate-css 1.4.0`,
    `server-only 0.0.1`, `@types/node 24.19.2`; `.npmrc` (`save-exact`, `engine-strict`). The BFF:
    `src/app/bff/[...path]` (allow-list generated from `docs/api/openapi.json`: 30 routes, auth routes excluded),
    `bff/login` (token → `ng_session` httpOnly + `ng_csrf`, `me` only to the browser), `bff/logout`; `src/proxy.ts`
    (next-intl + a CSP with a per-request nonce). `.claude/launch.json` entry `nilegate-web`.
  - **Design system** `web/design/MASTER.md` (DRAFT until the gate): the "tally office" idea — quiet paper and ink,
    the one bold thing is the **tally slip** of each number; the deck palette; Alexandria (display, an Egyptian
    designer's Arabic + Latin family) + IBM Plex Sans Arabic (text), both OFL, self-hosted by `next/font`.
  - **Concept** (sample data; W23 billing is the real golden-set value): `/ar/concept` (home: the waiting pack first,
    the ask panel, the services as a ledger), `/ar/concept/answer` (understood line, stepper, answer with number
    chips → tally slip, refused part, "How we know"), `/ar/concept/pack` (filmstrip, slide replica with chart, the
    Validator note pinned to its bullet, change panel). Same in `/en/…`; light / dark; mobile 375 without sideways
    scroll. `src/lib/receipts.ts` already uses the F0 span shape (`numbers: [{text, start, end, evidence_id, field,
    source}]`) and drops a span that does not match its text.
  - **Checks:** `npm --prefix web run check` → ✅ allow-list = OpenAPI, ✅ tsc, ✅ ESLint (RTL physical-class ban,
    `react/no-danger`, no `any`), ✅ Prettier, ✅ npm audit runtime high+ (0); Playwright **29 passed / 4 skipped**
    (logic 3; E2E desktop + mobile × ar + en: dir / lang, CSP with nonce, `nosniff`, `no-referrer`, no sideways
    scroll, axe 0 serious / critical, receipt opens and closes, language switch, `X-Frame-Options`, no console / CSP
    error, client JS runs under the CSP; BFF: 404 outside the schema, 405, 401 without a session, 403 cross-origin /
    no CSRF token, 422 login body) — on the dev server **and** on the production build (`CI=1`).
  - **D-FE-4 — every page renders per request:** with `generateStaticParams` the `[locale]` pages were prerendered,
    so Next's 23 scripts carried no nonce and a strict CSP would block them; the layout is `force-dynamic` now
    (23 / 23 scripts with the nonce). The first proxy matcher (object form with `missing` prefetch headers) did not
    run on locale paths; a plain string matcher `/((?!bff|_next|.*\..*).*)` does.
  - **D-FE-5 — deferred inside the plan, not dropped:** `shadcn init` / `components.json` to F2 (the concept used the
    pinned `radix-ui` Popover directly; the shadcn CLI installs its own dependencies, so it runs with
    `npm_config_before`), the Orval config to F0 (it needs the typed responses), Recharts to F5 (the concept's chart is
    a small SVG). npm 11 did not run three install scripts (`@parcel/watcher`, `@swc/core` via next-intl,
    `unrs-resolver` via eslint-config-next) — left unapproved, everything works on their prebuilt binaries. Dev-only
    audit: 10 moderate (minimatch via typescript-eslint); the gate is runtime high+.
  - **CI / repo:** `web` job in `.github/workflows/ci.yml` (Node 24, `npm ci`, static check, Playwright on the
    production build, report on failure); Dependabot `npm` for `/web`; `.graphifyignore` + `web/.gitignore`.
  - **Next:** the owner reviews the three screens (ar + en, light + dark) → `MASTER.md` to APPROVED (or changes);
    then F0 (after the approver plan's Phase F, D-FE-1 agreed with that session) and F2.
- 2026-11-06 — **Concept v1 rejected by the owner; v2 built (D-FE-6).** Owner: keep only the colours (blue and
  white); nothing of the design convinced; the UI tools were not visibly used; the look must carry logistics business
  + technology + analysis; **the interface in English**, only answers in the language of the question. Clickable
  choices: direction → "use all three" (night-ops hero + control-tower KPIs + bento), font → **Geist**.
  - **D-FE-6 (owner decision, changes §0 F6 and §8):** English-only interface; `next-intl` kept **without i18n
    routing** (`messages/en.json`, no `[locale]` segment, no locale proxy — the locale routing also made production
    redirect `/concept` to itself); RTL only inside model text (`dir="auto"` on the answer block; IBM Plex Sans
    Arabic as the font fallback); light theme only (the navy band is the one dark surface); the RTL physical-class
    ESLint ban kept for our code, off for the vendored `src/components/ui/**`.
  - **Tools used this time** (recorded in `web/design/MASTER.md`): UI UX Pro Max `--design-system` + style /
    chart / typography searches; dataviz (rules + `validate_palette.js`: all checks pass on white); Frontend Design;
    **shadcn/ui** `init -b radix -p nova` + `add button card badge input tabs popover separator avatar progress
    tooltip` (run with `npm_config_before=2026-10-23`). shadcn added the npm package `cn` (an unreviewed clsx +
    tailwind-merge replacement) — removed, `src/lib/utils.ts` keeps our `cn`; `shadcn` itself moved to
    devDependencies (only its CSS is imported at build). Inactive tab text raised from 60 % to 75 % for contrast.
  - **v2 screens** (`/concept`, `/concept/answer`, `/concept/pack`): LaneMap (dot-matrix land, Suez / Cape lanes,
    nine ports, six moving vessels, reduced motion respected), KPI cards with receipts + sparklines, bento (pack with
    slide strip, voyage radar, billing chart, route compare, overdue receivables as container rows, chart requests);
    a two-turn conversation (English, then an Arabic follow-up answered in Arabic RTL) with tool chips, trace, "How we
    know" side panel; the pack review with filmstrip, slide replica, Validator note, decision tabs.
  - **Checks:** `npm run check -- --static` all ✅; Playwright **25 passed / 4 skipped** on the dev server and on the
    production build (English UI, CSP nonce, no sideways scroll desktop + mobile, axe 0 serious / critical, Arabic
    answer computed RTL, receipt slip, lanes + vessels present, Radix tabs under the CSP, no console / CSP error,
    BFF rules unchanged). Note for F7: `next start` warns with `output: "standalone"` — the Compose image runs
    `node .next/standalone/server.js`.
  - **Next:** the owner reviews v2 → `MASTER.md` APPROVED or changes; then F0 / F2.
- 2026-11-06 — **D-FE-7 PROPOSED (not started):** the approver-plan session relayed a new owner requirement — show
  the Power BI finance dashboard smartly in the web, not only the pack (owner chose "In the frontend (recommended)").
  Folded in as §6.9 (pages, smart summaries, RBAC), the §2 endpoint rows, phase **F5b** and a done-when line. API
  addition named: `GET /api/v1/finance/weeks`, `GET /api/v1/finance/{dataset}?week=`, `GET
  /api/v1/finance/invoice-audit?week=` — thin wrappers over `finance_kpi` / `invoice_audit`, no new SQL, no KPI math.
  Also §0 F6 marked superseded by D-FE-6. **Waits for the owner's approval.**
- 2026-11-06 — **D-FE-7 APPROVED** by the owner ("موافق على D-FE-7"): §6.9, the §2 rows (now PLANNED) and phase F5b
  stand as written; F0b (the three read endpoints) joins F0, after the approver plan's API work; the Executive YTD
  source is still checked first. Nothing built yet.
- 2026-11-06 — **Concept gate passed: v2 APPROVED** by the owner ("موافق على v2"); `web/design/MASTER.md` → APPROVED
  and binding for every page. **F1 closed.** Next: F2 (login, shell, `/me`, health badge, logout, 404 — depends on F1
  only) while F0 / F0b wait for the approver plan's API work.
- 2026-11-06 — **F2 done** (owner: "ابدأ F2"). Handoff:
  - **Sign in** `/login` (night-ops side + form): one message for every wrong login, the lockout wait from
    `Retry-After`, "API not reachable" for 502; success → a full load of the same-origin return path (`safeNext`:
    no `//host`, no `/\`, no control characters, never `/login` or `/bff`).
  - **Gate:** route group `src/app/(app)/` — `getSession()` (server-only, React `cache`, one `GET /me` per request
    with the session cookie's token); no session or API down → `/login?next=…` (path from the proxy's
    `x-nilegate-path` header). Who the user is comes only from `/me` (no name in `Me` → "Employee 13, manager in
    Finance").
  - **Shell:** `AppTopBar` with the products menu from `/me` (`components/shell/nav.ts`; unbuilt pages show as
    "soon" with their phase, never as dead links), `HealthBadge` (`/health/ready` every 60 s: ready / degraded /
    offline, components in a tooltip), `UserMenu` (employee, role, department, sensitivity ceiling, Sign out →
    `/bff/logout`, which revokes the token at the API and clears both cookies). TanStack Query provider: retries only
    on 429 / 503 with `Retry-After`. `bffFetch` (client): same-origin, the CSRF header on unsafe methods, 401 → sign in.
  - **Today** `/`: the night-ops band + LaneMap, the greeting in Cairo time, the services the asker has, each with
    the phase that brings its page. **404** `not-found.tsx` ("not on the chart" — never "exists but hidden").
  - shadcn `add label alert dropdown-menu skeleton` (pinned date); it re-added the `cn` package → removed again.
    `/health/ready` is no longer treated as public by the BFF (it needs a session, ADR-064); `/health/live` stays.
  - **Tests:** a mock API `web/tests/mock-api.mjs` (login / logout / me / health on 127.0.0.1:8765, test logins in
    `web/tests/fixtures/users.json`, test hooks under `/__mock/*`, never in the BFF allow-list); Playwright now runs
    the production build on port 3100 against it (database-free, same in CI, never in the way of the dev server on
    3000). `tests/auth.e2e.spec.ts` (serial): signed-out → sign in; the sign-in page's CSP / frame headers + axe;
    wrong password message; lockout after 3 → "Try again in 2 minutes"; finance vs operations menus from `/me`;
    `ng_session` httpOnly + SameSite=Strict + Secure and absent from `document.cookie` / storage, `ng_csrf` present;
    the BFF sends `Authorization: Bearer` and **no cookie header** upstream; `next=//evil.example` → `/`; degraded
    badge; sign-out revokes the token (reusing it at the API → 401) and clears both cookies; 404 page.
    `npm run check` → all ✅ (Playwright **34 passed**, twice in a row, no flaky test).
  - Seen in the browser against the mock on port 8000 (the real API was not running): sign in, Today, the account
    menu, sign out.
  - **Next:** F3 (chat) needs the typed `RunEvent` union and the answer `numbers` of F0 / D-FE-1 for receipts; until
    then F3 can start on the existing endpoints with evidence chips per answer (the fallback of D-FE-1).
- 2026-11-06 — Owner: **F3 waits for F0** ("استنى F0"): no chat with fallback chips; F3 starts on the typed
  `RunEvent` union and the answer `numbers` (D-FE-1) once the approver plan's API work and F0 are done. The shadcn and
  Context7 MCP servers are connected (approved by the owner on the restart).
- 2026-11-07 — **F0 + F0b + D-FE-1 done** (owner: "تمام كمل", the approver plan's API work being finished —
  Phases A–H implemented 2026-11-06). Recorded as an ADR-064 note. Handoff:
  - `pipelines/api/schemas.py`: response models for every untyped 200 (packs list / view / report, questions,
    route advice, watch alerts / runs, the catalogue, promotion), `AnswerData`, the `RunEvent` discriminated union
    (+ `RunEventSchema` on the SSE route), `NumberSpan`. `runs.py` normalises the answer once (event = `RunOut.result`;
    `Api_check` Phase 4 now compares the typed shape). `auth.py`: `HTTPBearer(auto_error=False)` declares the scheme.
  - `GET /packs/{thread}` + `allowed` (decide, addition slides, caps, revisions left) + `charts_drawn` (from
    `render.build_spec`).
  - **D-FE-1** without touching any check or state: `slots.number_spans(template, evidence, rendered)` renders again
    and returns spans only when the text is identical; wired into `supervisor.answer_summary`,
    `route_advice.result_summary` (headline / reasons / risks) and `voyage_watch.result_summary` (headline / items).
    The approver session was idle with its API phases done, so no clash.
  - **F0b** `pipelines/api/routers/finance.py`: `/finance/weeks`, `/finance/{dataset}`, `/finance/invoice-audit`
    (`ytd=true` = weeks 1…week). **Executive YTD (uncertain point):** billing YTD is not a column of `finance_kpi`
    (the pack's YTD comes from `invoice_audit … through_week`); F5b decides with the owner whether the Executive page
    shows the audit's YTD or needs a view column (a migration, not API math).
  - `Serve.py --fake-roles` + `pipelines/api/fake.py`; `tools/export_approval_cases.py` → `web/tests/fixtures/
    approval_cases.json` (22 cases, 8 valid), `--check` in the CI's Python job.
  - **Checks:** `Api_check.py` 12 / 12 (Phase 11 new; Phase 7 asserts `allowed` / `charts_drawn`), `Memory_check.py`
    3 / 4 (Phase 4 = real models, opt-in as before), lint ratchet clean, OpenAPI snapshot 31 paths, web `npm run
    check -- --static` all ✅ (allow-list regenerated: 33 routes).
  - **Not done in F0 (moved):** Orval generation itself moves to F3, where the client is first used (the schema is
    now complete for it).
  - **Next:** F3 (chat) on the typed events and the number receipts.
- 2026-11-07 — **F3 done** (owner: "ابدأ F3"; asked once: assistant-ui as planned, chosen over our own thread
  components). Handoff:
  - **Typed client:** Orval 8.44.0 (`web/orval.config.ts`, `npm run gen:api`) → `src/api/generated/client.ts`
    (fetch functions through `src/api/mutator.ts` = `bffFetch`, body returned, errors as `BffError`) + `zod.ts`
    (runtime schemas; the run-event union validates every SSE event). `npm run check` regenerates and fails on a diff.
  - **Runs in the browser:** `src/lib/runs.ts` (fetch + `eventsource-parser`, zod check, unknown event dropped and
    logged, reconnect with `Last-Event-ID` ×3, then `GET /runs/{id}`).
  - **Thread:** `@assistant-ui/react@0.15.31` on `useExternalStoreRuntime` (`components/ask/AskThread.tsx`): our turns
    are the store; each assistant message carries its turn in `metadata.custom` and renders `AnswerCard` (trace from
    `queued` / `started` / `tool_called`, refused-tool chips, the answer as plain text with **number receipts from the
    API's `numbers`**, `dir="auto"`, the partial box, "How we know"). `useAskThread` (history = `GET /conversations/
    {id}` + `GET /questions/{thread}`; a first question opens the conversation and the address becomes `/ask/<id>`).
    `AskWorkspace`: recent conversations, documents (upload PDF / Word ≤ 5 MB → verdict; a manager / the CEO can ask
    for promotion). Pages `/ask`, `/ask/[conversationId]`; the menu's Ask is live and the home tile links to it.
  - **D-FE-8 (deviation, safer):** answers render as **plain text** (with receipts), so `@assistant-ui/react-markdown`
    and `rehype-sanitize` are not installed; Markdown can come later behind the same sanitising rule if answers need
    lists or tables. A clarify / ask-back shows the API's question; the reply goes through the composer (the API sends
    no option list).
  - Fix found in the browser: a number chip opened by hover was closed again by the click → a click now only opens.
  - **Tests:** the mock API gained conversations, questions as runs with SSE events, runs, questions, uploads
    (English / Arabic answers with spans; a non-Finance asker gets `tool_refused` + `not_permitted`).
    `tests/ask.e2e.spec.ts`: trace → answer → receipts (field / view / filter) → "How we know" + axe; Arabic follow-up
    computed RTL; reload = history with receipts; refused tool and no figures outside Finance; upload verdict + list.
    `applyEvent` logic test. Two shared-mock races fixed (lockout probe address; last request per token).
    `npm run check` all ✅ — Playwright **39 passed**, three runs in a row.
  - **Not verified:** the real API in the browser — it has no login yet (`Api_admin.py list` = 0; logins are the
    owner's). With one test login: `$env:API_FAKE_ROLES = "1"; uv run python pipelines/scripts/api/Serve.py
    --fake-roles` and the dev server.
  - **Next:** F4 (weekly pack review) — its endpoints and `allowed` / `charts_drawn` are ready.
- 2026-11-07 — Owner: "اعمل login اختبار" + "اعمل ايميلات الموظفين": 11 test logins (one per role × department +
  the CEO) created with `Api_admin.py create --password-stdin`; emails listed by `Api_admin.py list`, passwords only in
  the git-ignored `web/.env.local` (`WEB_E2E_<ROLE>_<DEPT>_*`). `<html suppressHydrationWarning>` restored (a browser
  extension adds attributes). The API in `--fake-roles` mode started (health/live ok); the browser check of the chat
  on the real API is **not done yet** (usage limit) — next step.
- 2026-11-07 — **The chat checked on the real API** (owner: "Try again"): the API in `--fake-roles` mode over the real
  databases + the dev server; `web/scripts/real-api-smoke.mjs` (by hand, logins read from `web/.env.local`, never
  printed): ✅ the Finance manager signs in; ✅ the answer carries 3 receipts (billed 8,394,785.98 SDR = the golden
  value, budget, collected); ✅ the first receipt = `billed_sdr` / `finance.kpi_weekly` / `report_week = 23`; ✅ an
  operations employee is refused with no figures. The owner's two screenshots were not code errors: the API was
  stopped ("not reachable"), and `GET /` on the API is a 404 by design (its routes are under `/api/v1`, docs at
  `/docs`). The allow-list (36 routes) and the Orval client regenerated for the approver-request plan's three routes.
- 2026-11-07 — **D-FE-9 (APPROVED by the owner 2026-11-07, "موافق على D-FE-9"; built in F4 / F5b; from the approver-request plan, `docs/archive/2026-11-07_Approver_request_plan.md`, ADR-067
  §2b–§2c):** (a) §6.4 pack review: a "Write your request" box → `POST /packs/{thread}/request` (a run; its answer is
  a proposal: `understood`, `steps`, `ask_back`, `draft_sha`, `reread_text`) → the UI shows what was understood and the
  steps, then **Confirm** → `POST /packs/{thread}/request/confirm` (409 `stale` when the draft changed → "the pack
  changed, read it again"); nothing is applied before Confirm. (b) §6.9 `/finance`: a "This week's pack" panel from
  `GET /finance/pack?week=` (summary, the two charts as ViewSpecs, approver and time, `degraded`). Both fit F4 / F5b.
  **Waits for the owner's approval.**
- 2026-11-07 — **F4 + D-FE-9 (request box) done** (owner: "ابدأ F4"). Handoff:
  - `/packs` (list: week, attempt, waiting / ended / stopped, status; the approval report link for deciders),
    `/packs/[thread]` (`PackReview`: filmstrip of the 10 slide titles with Validator flags, the slide as a light
    replica with indexed bullets, "Approver's addition" marks, the Validator notes pinned to their bullet, the deck's
    own charts from `charts_drawn` drawn by `PackChart` (SVG, the dataviz rules), banners for `redrafted` /
    `degraded` / readiness, the decision log, downloads of the preview PPTX and the published deck through the BFF),
    `/packs/report` (counts, edit rate, approvers' changes). Menu "Weekly pack" live.
  - `DecisionPanel` (only when `allowed.decide`): **Request** (D-FE-9: words → `POST /request` run → "Understood as"
    + the steps in plain words → **Confirm** → `POST /request/confirm`; a changed draft → 409 `stale` → "The pack
    changed since this was understood"), **Edit** (bullet text, one addition on allowed slides within the caps),
    **Revise** (a steer; revisions left shown), **Decide** (approve with an optional comment; reject needs one). Every
    body passes `src/lib/decision.ts` first; a run streams its nodes; the view reloads when it ends.
  - `src/lib/decision.ts` = the API's `DecisionIn` rules: `tests/decision.logic.spec.ts` runs them on the 22 exported
    cases (`approval_cases.json`) — all agree with the server.
  - Not in F4 (kept for F5, which brings the catalogue form): the chart-variant picker and the analysis-notes editor
    (`analysis_edits` beyond a steer); the request box already covers both in words.
  - **Tests:** the mock API gained one pack (list / view / preview / decision / request / confirm / report, a stale
    draft sha, a Finance employee who reads but cannot decide). `tests/packs.e2e.spec.ts`: review + Validator note +
    chart + axe; request → understood → Confirm applies; stale refused; client rules before sending; approve →
    published + report; a reader without the panel; 404 outside Finance. Two more test races fixed (the last request is
    now per token **and** path; the composer is used only after hydration — `real-api-smoke.mjs` waits the same way).
    `npm run check` all ✅ — Playwright **67 passed**, three runs in a row.
  - **Next:** F5 (views + chart variants + the analysis editor), then F5b (finance pages + this week's pack panel), F6.
- 2026-11-07 — **F5 done** (owner: "ابدأ F5"). Handoff:
  - **Recharts 3.10.1** installed (owner F3; `npm_config_before`). One chart component `components/viz/SeriesChart.tsx`
    (line / bar, one unit per axis, `null` = a gap, the deck colours, a legend for 2+ series, a tooltip) + `SeriesTable`
    (the same numbers as a table under "Show the numbers", `data-value` = the API's raw value). The pack's
    `charts_drawn` now draw through it too (`PackChart`), so the web has one way to draw.
  - **`/views` (Charts):** ask in words (`POST /views {question}` → run → the drawn view, or the API's ask-back
    question, or not permitted) or choose from `GET /charts/catalogue` + `GET /finance/weeks` (kind, week, series ≤ 3
    of one unit, 4 / 8 / 13 / 26 weeks, measure, rows, compare week → `POST /views {choice}` → `ViewSpec`); the
    caption is the API's; the sources listed (`view — filter`). Menu "Charts" (finance readers) + a home tile.
  - **Pack decision panel (carried from F4):** a **Chart** tab (trend series / weeks or variance measure / rows from
    the catalogue → an `edit` with `charts`) and the **analysis editor** in Revise (summary points replaced, a caveat
    added, the steer optional when an analysis edit is given).
  - Found on the real API: a ViewSpec's sources carry `view` (not `name`) → the page and the mock fixed.
  - **Tests:** the mock gained the catalogue, the weeks and `/views` (choice, question, ask-back, refusal); the pack
    view gained Insight notes. `tests/views.e2e.spec.ts` (choice drawn, caption, source line, a null shown as "—",
    the table's raw values, axe; a question drawn; an ask-back; no Charts outside Finance) + the chart / revise test in
    `packs.e2e.spec.ts` (one pack, so one serial file). `npm run check` all ✅ — Playwright **71 passed**, three
    runs in a row. `real-api-smoke.mjs` on the real API (`--fake-roles`): **5 / 5** (+ a chart by choice from the real
    views: 26 values).
  - **Next:** F5b (the finance pages + this week's pack panel, D-FE-7 / D-FE-9), then F6 (route advice, the watch).
- 2026-11-07 — **F5b done** (owner: "ابدأ F5b"; D-FE-7 + the D-FE-9 panel). Handoff:
  - `/finance` (`components/finance/FinanceDashboard.tsx`): one week picker for every page (the URL keeps `week` and
    `page`), tabs **Overview** (KPIs with receipts + WoW, billed / budget / collected 13 weeks), **Revenue** (billed vs
    budget by vessel category), **Receivables** (ageing buckets, overdue roll-forward, the overdue list), **Customers**
    (13-week ranking, watchlist), **Exceptions** (the invoice audit: checked, flagged, at stake, manual review,
    findings), **Executive** (13-week position, on-time payment, KPIs + **"This week's pack"** from
    `GET /finance/pack`: approver, time, `degraded`, the approved summary, its charts), **Smart View** (the Charts
    workspace). Every page opens with two lines chosen by fixed code rules (which field moved most, which bucket is
    largest, how many rows meet a flag) — a choice among the view's own fields, no new arithmetic (ADR-047). Menu
    "Finance" live.
  - **Executive YTD (the uncertain point of F0b):** shown as the 13-week position (`budget_variance_13w_pct`,
    `billed_13w_sdr`), which the view holds; a calendar YTD billing figure needs a view column (a migration) — left for
    the owner to ask for.
  - The FastAPI P6m session's last update read first (owner): the approver-request plan is archived
    (`docs/archive/2026-11-07_Approver_request_plan.md`, ADR-067; reference here updated); D-AR-9 turns a step the
    pack would refuse into an **ask-back** before the confirm — the F4 request box already shows `ask_back` instead of
    Confirm; no new event, no schema change (OpenAPI 34 paths, allow-list and client in step).
  - **Tests:** the mock gained the five datasets, the invoice audit and `/finance/pack` (W45 published, others 404);
    `tests/finance.e2e.spec.ts` (Overview summary + receipt + trend + axe; every tab; the URL keeps week / page;
    Executive with and without a published pack; 404 outside Finance). `npm run check` all ✅ — Playwright **75
    passed**. **Real API** (`--fake-roles`, `real-api-smoke.mjs` **7 / 7**): Overview week 23 billed 8.39M SDR with
    its receipt (= the golden value); Executive **W15 = the pack published live through the API** (billed 3.77M SDR =
    the deck's 3,767,281.17; its 8-week Billed / Collected chart = the manager's request).
  - **Open for the done-when:** the owner's hand-check of one week's Overview against Power BI Desktop (the P6m
    session already matched W15's 16 numbers API = Power BI).
  - **Next:** F6 (route advice, voyage watch, the React Flow run view), then F7.
- 2026-11-08 — **F6 done** (task from the frontend session; owner usage saved in a side session). Handoff:
  - **`/routes`, `/routes/[thread]`** (`components/routes/RouteWorkspace.tsx`, `RouteDecision.tsx`, `RouteStrip.tsx`,
    `src/lib/route-advice.ts`): the form checks `RouteIn`'s own rules before sending (UN/LOCODE pattern, origin ≠
    destination, a vessel id **or** type + condition + SCNT, speed 4–25) → `POST /route-advice` (a run) → a stepper
    from the allow-listed `ROUTE_NODES` → `/routes/<thread>`. The decision view: Suez | Cape cards from `comparison`
    read through zod (route rows + the difference row; a row outside the shape is left out, never guessed), the
    recommended card badged, the line "saves X SDR · −Y days" from the graph's own `route.difference` (Cape − Suez):
    the browser only chooses the words and the sign by a comparison and shows the absolute value with
    `Intl.NumberFormat` `signDisplay: "never"` — no arithmetic; headline / reasons / risks with **number receipts**
    (`numbers.headline` / `reasons[i]` / `risks[i]`); a note per non-ok status (`no_suez_on_route`, `suez_only`,
    `not_permitted`, `no_data`, `output_invalid`, `validation_failed`); "How we know" (assumptions, sources,
    problems, model calls, receipt count); the SVG strip origin → Suez / Cape → destination; earlier advice
    (`GET /route-advice`, date + `#n`).
  - **`/voyages`, `/voyages/runs/[thread]`** (`components/voyages/VoyageWatch.tsx`): the radar list of
    `GET /voyage-watch/alerts` (filter **High only / All** in the URL, `?high=1`; "Showing n of m"; `not_permitted` /
    `no_data` are answers, shown calmly), `Radar` from `viz/charts.tsx` (ring by severity, angle by list place — a
    layout, not a value; keys made unique per blip), rows with severity, kind, destination and ETA; the run's brief
    (`GET /voyage-watch/runs/{thread}`: headline + items with receipts from `numbers.items[i]`, eight fleet counts,
    "How we know"); the runs list (newest 20). Read only.
  - **§6.8 run graph** (`components/packs/RunGraph.tsx`): `@xyflow/react` **12.12.0** (published 2026-09-24, MIT;
    deps `zustand`, `classcat`, `@xyflow/system 0.0.83`; installed with `npm_config_before=2026-10-23
    --save-exact`; only `base.css`), loaded by `next/dynamic` (no SSR) in `DecisionPanel` and shown **only for a
    decision run** (Decide and Confirm; the request run is a proposal and keeps the plain line): the nine
    allow-listed `weekly_pack` nodes (`PACK_NODES`) in three columns, a custom step node with hidden side handles,
    the current node filled, passed nodes outlined, edges between passed nodes blue; static (no drag, zoom, select,
    focus); attribution hidden (MIT, non-commercial educational project).
  - Menu: Routes and Voyages live (`nav.ts` phase `null`); the home tile text no longer promises ETA drift.
    `.claude/launch.json` gained `nilegate-api-fake` (the API with `--fake-roles`, `API_FAKE_ROLES=1`).
  - **Deviations / open points (D-FE-10, for the owner):** (a) **ETA drift** is not shown: `WatchAlert` /
    `WatchRunDetail` do not carry the run file's `etas` (rule ETA vs schedule) or `eta_in_h` — it needs an API field
    (a small `schemas.py` + `result_summary` change), not browser arithmetic; (b) `SeriesChart` not used: the watch
    endpoints give one run's counts, no series (the Radar is reused); (c) URLs `/routes` and `/voyages` (the menu's
    names since F2; D-FE-6 dropped the locale segment) instead of §6.6–§6.7's `/route-advice`, `/voyage-watch`;
    (d) **API gap found:** plan §6.7 says watch runs are for Operations + the CEO, but `GET /voyage-watch/runs` and
    `/runs/{thread}` check only a signed-in user (`routers/operations.py`) — the page shows what the API returns; to
    be closed in the API (F7 security pass or its own fix), not in the browser.
  - **Tests:** mock API: route advice (runs with `node` events, stored threads, owner check, a `no_suez_on_route`
    case) and the watch (two saved runs, one without a brief; filters; `no_data`); `tests/routes.e2e.spec.ts` (5:
    steps → cards → saving line → strip → receipts → How we know + axe; earlier advice after a reload; no canal;
    the form's rules send nothing; another employee's advice 404; no Routes outside Operations),
    `tests/voyages.e2e.spec.ts` (3: radar list, High only in the URL and after a reload, brief receipts, fleet, axe;
    an earlier run without a brief; unknown run; no Voyages for the Finance manager),
    `tests/operations.mobile.e2e.spec.ts` (phone width: no sideways scroll + axe on both pages), and the pack request
    test now asserts the run graph (Validator lit, run finished). `npm run check`: Playwright green three runs in a
    row; the first three runs showed ❌ Prettier on `viz/charts.tsx` (edited outside the format hook) and once ❌
    `npm audit` (a network failure; 0 vulnerabilities on re-run) → fixed, then all ✅, **84 passed** (40 skipped =
    the desktop-only / mobile-only splits).
  - **Real API** (`--fake-roles` + the dev server; `real-api-smoke.mjs` **13 / 13**): the watch's latest saved run =
    12 alerts of 12, 297 vessels watched, the brief's 7 receipts naming `watch.*` evidence, High only = 3 of 12, the
    runs list (15 runs); route advice: 8 stored advice (SGSIN → NLRTM), the first opens with its cards — its saving
    line 111,198.30 SDR · −10.38 days agrees with the cards (696,355.18 / 585,156.88 SDR; 35.35 / 24.97 days).
    A new advice needs a real model (the fake roles do not script the advisor). Screenshots in
    `Notebooks/_scratch/f6/` (sent to the owner).
  - **Next:** F7 (Compose, security E2E, DevTools pass, real-model smoke incl. one route advice, docs, archive).
- 2026-11-08 — **D-FE-10 decided and built** (owner, clickable: "D-FE-10 first, then F7"; ETA: "add it now", then
  "the ETA board" once a schedule ETA turned out not to exist). Handoff:
  - **Watch runs access:** reading ADR-006 again corrected the F6 note — the runs are level-1 Operations data that
    **every employee** may read (`retrieval.allowed`; `rbac_mapping.md`; `Api_check.py` Phase 8 asserts it), so §6.7's
    "Operations + CEO" was narrower than the ADR and is not applied (ADR above plan). What was missing was the
    identity check itself: `GET /voyage-watch/runs` and `/runs/{thread}` now call `watch.can_read` like the alerts
    and the CLI (refusal → 403 `not_allowed` + an audit row). No employee is refused today (every ceiling ≥ 1).
  - **ETA board instead of "drift vs schedule":** a run holds only rule R's ETA (`eta_utc`, `eta_in_h`, distance
    left, speed) — the schedule's arrival is the voyage file's `arrival_ts`, the evaluation's answer key, never
    returned before arrival (ADR-055). `WatchRunDetail.etas` (new `WatchEta` model) carries the run's ETA table;
    `/voyages` shows an **ETA board** (alerted vessels first, then soonest; hours to go as a scale bar beside the
    API's number; distance left · speed; "Suez ahead"; 12 rows, then all on demand; a focusable scroll region on a
    phone). ADR-064 note. OpenAPI 34 paths (unchanged), Orval client regenerated, allow-list 36 routes, lint ratchet
    0. `Api_check.py` could not run: its Phase 0 needs one employee **without** a login per profile and the 11 test
    logins took the only CEO (an environment fact, logins kept) — verified on the running API instead: runs 200 for
    an operations employee and a Finance manager, 297 ETA rows, 219 with an ETA (= the vessels in transit).
- 2026-11-08 — **F7 done (what Claude can do; the owner's checks below).** Handoff:
  - **Compose (§11.2):** the uncertain point tested first — from a `node:24.20.0-slim` container,
    `http://host.docker.internal:8000` reaches the API bound to 127.0.0.1 on Docker Desktop, so **no fallback**.
    `compose.yaml` (root, one service `web`), `web/Dockerfile` (deps → build → run, the standalone output, user
    `node`), `web/.dockerignore` (`.env*` never in the context); the service: `127.0.0.1:3000`, read-only root, tmpfs
    for `/tmp` and the Next cache, all capabilities dropped, `no-new-privileges`, `NILEGATE_WEB_ORIGIN =
    http://localhost:3000` (open that origin: the CSRF Origin check compares it). `docker compose up -d web` + the
    real-API smoke **against the container: 14 / 14** (incl. the ETA board: 219 vessels at sea).
  - **Security E2E (§10.5)** `tests/security.e2e.spec.ts`: an answer carrying `<script>`, `<img onerror>`, a
    `javascript:` link, a Markdown image and an outside link renders as characters (no element, no script run, no
    dialog, **no request leaves the origin**); **every page** (`/`, `/ask`, `/packs`, `/packs/report`, `/views`,
    `/finance`, `/routes`, `/voyages`): 200, the CSP with its nonce, `frame-ancestors 'none'`, `object-src 'none'`,
    `X-Frame-Options`, `nosniff`, `no-referrer`, **axe 0 serious / critical**. The injection set holds no HTML / JS
    shapes (it is LLM01 prompt injection), so the four shapes named in §10.5 were used. Token storage, CSRF,
    allow-list refusals stay in `auth` / `bff` specs.
  - **Performance (§10.7, light, no gate)** on the production container + the real API: Lighthouse on `/login`
    (Chrome DevTools MCP): Accessibility 100, Best Practices 100, Agentic Browsing 100, SEO 50 by design
    (`noindex`, no meta description — an internal app). Signed-in pages (Playwright timings, cold): TTFB 21–111 ms,
    LCP 60–352 ms (the slowest: a pack review, 352 ms), 33–56 requests; decoded JS ≈ 0.7 MB on most pages, ≈ 1.2 MB
    on Ask (assistant-ui), Finance and the pack review (Recharts) — a finding, not a problem; revisit only if a page
    feels slow.
  - **Review (§9a):** the `security-review` / `code-review` skills read git, which the project's hook blocks for
    Claude, so the security core was reviewed by hand (BFF proxy, login / logout, core rules, proxy CSP): no defect
    (fixed upstream, allow-list with segment patterns, three CSRF layers with a constant-time compare, header
    allow-lists both ways, limits before reading a body, cookies cleared on a 401, one message for every failed
    sign-in). Note: the browser's `x-request-id` is forwarded to the API as is (the API's own validation applies).
    The owner may still run `/security-review` before the commit.
  - **Docs:** ADR-060 amendment 3 (BFF cookie session + CSRF + allow-list, the F0 contract, English UI / plain text,
    the libraries, Compose scope, tests), ADR-064 note (D-FE-10), ARCHITECTURE (§2 web row + Compose row, §7 web
    interface, §8 web dependencies, §9 ADR-060 row), `docs/THREAT_MODEL.md` (a Web UI table: XSS, token theft, CSRF,
    open proxy / SSRF, clickjacking, exfiltration, access in the browser, npm supply chain, container; LLM05's gap
    closed), ROADMAP. `/graphify . --update` and the archive wait for the owner's checks below.
  - **Tests:** `npm run check` all ✅ three clean runs in a row — Playwright **93 passed** (49 skipped = the
    desktop-only / mobile-only splits), no test server left behind. Found on the way: the Ask page had no `<main>`
    landmark (axe rates it moderate, so no earlier spec caught it) → `AskWorkspace` is a `<main>` now; the
    every-page sweep split into one test per page (one 30 s budget for eight pages with axe was too tight). Note:
    two Playwright runs at once fight for ports 8765 / 3100 and a run that stops at start-up leaves its mock alive —
    run one check at a time.
  - **Open for the done-when (the owner's, by design of §10.6 / §12):** (1) the real Monday pack (2026-11-09)
    decided through the UI with at least one approver change; (2) one EN + one Egyptian Arabic question with a
    follow-up, one view question and one route advice on the **real models** (not `--fake-roles`); (3) the hand-check
    of one week's Overview against Power BI Desktop (D-FE-7); (4) the CI `web` job green on the pushed branch. Then:
    the implementation record, the archive, `/graphify . --update`, and the owner's one commit.
- 2026-11-11: PortPilot rebrand (owner-requested) completed in the UI, metadata, icon, BFF configuration and client
  artifacts. Shared `Brand.tsx` supplies the P/navigation mark on light/navy backgrounds. Old environment keys
  remain fallback aliases; cookie names remain compatible. Production browser suite: 100 passed / 50 intentional
  skips, including desktop/mobile branding, icon, EN/AR, CSP and axe. Six screenshots captured; desktop login,
  mobile home and desktop answer visually inspected. `preview_start` is unavailable; Playwright supplied the
  browser proof. Initial build caught the error-page's old Logo import; repaired before the passing rerun.
  Real-model/UI approval/Power BI/pushed-CI acceptance above remains open. Rebrand details: `docs/brand/README.md`.
- 2026-11-11 stabilization R9: pack review and Finance/Executive show pending, unverified or superseded
  publication sync without hiding the approved deck. OpenAPI/client regenerated with `publication_sync`.
  Static checks all pass; 102 browser cases passed in the full run, then the corrected four publication cases
  passed on desktop/mobile (all 104 runnable cases covered; 50 intentional skips). Initial finance test opened
  Overview instead of Executive; fixed test navigation. Screenshots inspected, axe serious/critical 0 and no
  horizontal overflow. Owner live Power BI/database checks remain open; see `docs/publication_recovery.md`.
- 2026-11-12 stabilization R7: accepted-run reload recovery across Ask, routes, charts and pack actions. The
  signed-in header shows an explicit Resume/Refresh panel; only run IDs/page paths enter account-scoped tab
  storage, cleared on sign-out/account switch. No POST is replayed; approval interpretations stay unconfirmed.
  Owner-authorized GET/SSE restores answers/receipts/charts or links to persisted history. API restart/expiry,
  storage denial and the pre-accepted-response window are documented in `docs/api/run_recovery.md`.
  Production browser suite: 122 passed / 50 intentional skips; frontend static all pass. EN/AR desktop/mobile
  screenshots inspected, axe serious/critical 0 and no horizontal overflow. Initial mobile readiness/navigation
  and collapsed-table test assumptions corrected. Next: owner integration and existing live acceptance gates.
- 2026-11-12 runtime diagnosis: owner still sees NileGate because `project-web-1` runs the November 8
  `nilegate-web:local` image; HTTP /login confirms the old title. Source/compose now use PortPilot, but the running
  container was not rebuilt. API port 8000 is not listening (health connection refused). Next owner rollout:
  `docker compose up -d --build web`, then start the host API and verify live branding/health. Prior Playwright
  proof tested an isolated production build, not this retained service. No restart/build performed during diagnosis.
- 2026-11-14 — **D-FE-11 APPROVED and built the same day** (owner request, side session; written PROPOSED first,
  the four decisions asked once as clickable choices, all taken as recommended — see the handoff below): two changes
  to the shell and the Ask page.
  - **(a) Attach documents from the first message.** *Why it waits today:* the upload route is
    `POST /conversations/{id}/uploads` and the web opens the conversation (`POST /conversations`) only inside the
    first question (`useAskThread.ask`), so `AskWorkspace` shows "Ask a first question to attach documents" until
    then; the Documents panel is also `hidden lg:block`, so a phone cannot upload at all. `POST /conversations` is
    its own route and an upload into a conversation with no turn is already allowed by the API
    (`conversation_for(write=True)` + `sessions.get(create=True)`) → **web-only change, no API / OpenAPI / Python
    change**, every server check stays as it is (validator, screening, 5 MB, PDF / DOCX, 5 documents / 300 chunks per
    conversation, owner check, the conversation held busy during an upload).
    *Design:* a "+" button at the start side of the composer (`AskThread`) with a hidden multi-file input; picked
    files become chips above the input (name, state, remove). The conversation is opened when it is first needed —
    by the first attached file or the first question, whichever comes first (one shared `ensureConversation()` in
    `useAskThread`). Files upload one after another (the API holds the conversation busy per upload; parallel
    uploads would meet its 409). Comfort checks in the browser before sending (type, 5 MB, 5 per conversation) —
    the API decides. A refused file shows the API's message on its chip; the document's text is never shown. The
    sent question's bubble lists the names of the documents attached with it. The Documents panel keeps the list,
    the verdicts and the promotion request.
    *Owner decisions asked once (clickable):* when the upload starts (on pick vs. with Send), where "+" sits when
    the question is Arabic, the Documents panel's own Upload button, how the limits are shown.
  - **(b) The "Today" tab removed.** "Today" and the PortPilot wordmark both open `/` (`nav.ts` + `AppTopBar`), so
    the entry leaves `NAV`, `/` stays exactly the page it is, and the wordmark is the way home; no route is deleted,
    so no redirect is needed. The 404 page's "Back to Today" becomes "Back to home". The concept screens
    (`/concept`, their own `TopBar`) are the approved F1 gate record and stay as they are.
  - **Tests planned:** mock API reads the uploaded filename and refuses a planted name (422 `upload_refused`);
    `ask.e2e.spec.ts`: a new conversation's first message with two attached documents (English) and one in an Arabic
    question (RTL text, "+" position), a refused file, the client limits, the phone width (the "+" reachable, no
    sideways scroll, axe); `auth` / `security` specs: no "Today" link, the wordmark opens `/`. `npm run check`.
  - **Owner decisions (2026-11-14, clickable, all "recommended"):** (1) a picked file **uploads at once** (the chip
    shows the verdict before Send; known cost: a picked file without a question leaves an empty conversation in the
    list); (2) "+" stays **at the left always**, also when the question is Arabic (the interface is English, D-FE-6;
    only the text in the box turns); (3) the Documents panel's own **Upload button removed** — "+" is the one way
    in, the panel keeps the list, what the screening removed and the promotion request; (4) only the **tab** is
    removed, `/` stays the page it is.
  - **Handoff (built):**
    - `components/ask/useAttachments.ts` (new): the chips' state; comfort checks `localProblem` (PDF / DOCX,
      5 MB, 5 per conversation); uploads one after another through the generated client; a refused file shows the
      API's `upload.message` (never document text); removing an accepted chip calls the API's `DELETE …/uploads/{id}`;
      `takeSent()` hands the accepted names to the question and clears the chips.
    - `useAskThread.ts`: `ensureConversation()` (one `POST /conversations` shared by the first attached file and the
      first question), `ask(question, attachments)`, `Turn.attachments` (names in the bubble — this session only:
      the API keeps no link between a turn and its documents, so a reloaded history shows them in the panel, not in
      the bubble).
    - `AskThread.tsx`: "+" (44 px, `Attach documents`, a hidden multi-file input) before the box, Send after it;
      chips (`data-state` uploading / accepted / refused, `aria-live`) + the limits line above the box; "+" is off
      while an answer runs (the API holds the conversation busy) and Send is off while a file is being checked.
    - `AskWorkspace.tsx`: the Documents panel reads the API's list (with "n section(s) removed by the screening").
    - `lib/bff/client.ts`: `BffError.problem` = the API's problem body (to read a refusal's `upload` member).
    - `shell/nav.ts`: no "Today" entry; `app/(app)/page.tsx` unchanged but for its name / comment;
      `app/not-found.tsx`: "Back to home".
    - **The feature itself needed no Python, API, OpenAPI or allow-list change**; every server check is as it was.
      (The real-API smoke later found a defect in the upload reader's child process — fixed, see below.)
  - **Tests:** mock API: the upload reads the file name, checks the conversation's owner, refuses a planted name
    and the sixth document with the API's 422 shape, marks a planted name as screened, takes 300 ms, and has
    `DELETE …/uploads/{id}`. `tests/ask.e2e.spec.ts` (+4, the old panel-upload test replaced): the first message
    with two documents ("+" left of the box, Send off while checking, the conversation opened before any question,
    names in the bubble, the panel, axe, reload); an Arabic first question (box `rtl`, "+" still left, Arabic file
    name, Arabic answer RTL); refused / wrong type / too large / screened / remove; the sixth document stopped; no
    "+" without the uploads product. `tests/ask.mobile.e2e.spec.ts` (new): a phone attaches three files (44 px
    target, no sideways scroll with a long file name, axe) and asks in Arabic. `tests/auth.e2e.spec.ts`: no "Today"
    link, the wordmark opens `/`, "Back to home".
  - **Found on the way (test infrastructure, fixed because it failed the suite):** `recovery.e2e` (pack request /
    decision) depended on the one mock pack that `packs.e2e` decides in another worker — a race that the new specs'
    scheduling made visible (it failed in two full runs, passed alone). The recovery spec now reads a waiting
    pack's view from a read-only mock hook (`/__mock/pack-fresh`), so it neither depends on that state nor changes it.
  - **Checks:** `npm --prefix web run check` all ✅ (static 6 / 6; Playwright **130 passed**, 50 intentional skips)
    and a second full Playwright run 130 passed. A third run had one failure in `finance.e2e` ("Overview: old Smart
    View bookmarks…"): its hydration wait `getByRole("status", { includeHidden: true })` meets Recharts' tooltip
    (`role="status"`) when the chart draws before the API badge settles — a strict-mode flake in a file this task
    does not touch; **left as a follow-up** (filter the locator by the badge text). Screenshots (production build +
    mock API, desktop + phone, EN + AR) in `Notebooks/_scratch/dfe11/`, inspected.
  - **Web container rebuilt** later the same day (`docker compose up -d --build web` → `portpilot-web:local`,
    `/login` 200 with the new code), once the owner had Docker Desktop running again.
  - **Real API (the owner started it; real models):** `node web/scripts/attach-smoke.mjs` (new, by hand: the
    Operations test login from `web/.env.local`, the reviewed upload fixtures, the upload golden question u01 in
    English on desktop and u01_ar on a phone) — **12 / 12** against the rebuilt container: `clean_D1.pdf` accepted;
    `inj_visible_en.pdf` accepted with 1 section removed by the screening; `shape_missing_purpose.docx` refused with
    the API's own reasons (`E_LEVEL_ABOVE_UPLOADER`, `E_MISSING_SECTION`); the conversation opened by the first
    attached file, before any question; the first question's bubble names its documents; **the answer comes from
    the attached document** ("within 30 minutes", evidence `search_documents → qdrant:nilegate_docs + conversation
    uploads`) in English and in Egyptian Arabic (RTL, "+" at the left, no sideways scroll on the phone). The two PDFs
    are one document (NG-OPS-PRC-0042), so the later upload replaces the earlier and the panel lists one.
    Screenshots in `Notebooks/_scratch/dfe11/real/`, inspected.
  - **Server defect found by that smoke and fixed (owner's choice, clickable: "fix the reader"):** on the first
    real run every upload was refused with `E_PARSE`. `pipelines/lib/upload_reader.py` (the isolated child of
    `uploads.read_isolated`) wrote its JSON with a text `sys.stdout.write`, i.e. in the console code page: started
    from a plain PowerShell (cp1252, no `PYTHONIOENCODING`) the child died on a ligature (PDF → `RuntimeError`) or
    sent bytes the parent could not decode (DOCX → `UnicodeDecodeError`). The project's runners (`tools/run.py`,
    `ops/tests/run_api_integration.ps1`) set `PYTHONIOENCODING=utf-8`, so no check had seen it, and the web's
    uploads had only ever met the mock API — the old Upload button would have failed the same way. Fix: the child
    writes UTF-8 bytes (`sys.stdout.buffer`); no validation, screening or limit changed. Guard:
    `Upload_validation.py` Phase 4 now runs the reader under a forced cp1252 console and asserts exit 0 + UTF-8
    JSON. Checks: `Upload_validation.py` all phases ✅ (52 cases as expected; run directly — `tools/run.py`'s
    snapshot hit a file locked by the running API), `tools/lint_ratchet.py` ✅ (ruff 0, pyright 0). The reader is
    spawned per upload, so the running API picked the fix up without a restart. `Api_check.py` not run (it starts
    its own app and was not needed to prove the child's output; its upload phase goes through the same reader).
  - **The `finance.e2e` flake fixed** (owner: "fix it here"): its hydration wait now finds the API badge by its text
    (`[role="status"]` filtered by "API ready | degraded | offline", count 1) instead of by the role alone, which
    Recharts' hidden tooltip shares. `finance.e2e` ×3 each: 24 / 24; then `npm --prefix web run check` all ✅ and
    one more full Playwright run: **130 passed** twice in a row (50 intentional skips).
  - **Open:** the owner's commit (explicit paths).
