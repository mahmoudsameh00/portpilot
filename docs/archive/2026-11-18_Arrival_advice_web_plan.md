# Plan — Arrival advice in the web (ADR-070 → the API and the web)

**Status: IMPLEMENTED (2026-11-18).**

## Implementation record

- **Built:** `POST / GET /arrival-advice` and `GET /arrival-advice/{thread}`; the watch's `arrival` node (every `jit` /
  `rta_late` vessel advised in the run); on Voyages the advice under its alert, "Advise arrival" for any vessel at sea,
  and the page `/voyages/arrival/<thread>`; "Compare routes" from a Cape option. ADR-070 amendments 1 and 2.
- **Results:** `Voyage_watch_check` ✅, `Arrival_advice_check` Phases 1–7 ✅, `Supervisor_check` ✅,
  `Supervisor_tools_check` ✅, lint 0, `npm run check` ✅. Run before the last supervisor change: the stack suite 17 / 17
  and the full-data `Api_check` 12 / 12 (both re-run on the merged tree by the staging plan). Real models:
  the watch at the clock (53 alerts, 41 advices), Stage 2 `stage2_eval_2026-11-18_fold1.json` (every gate met, ADR-052
  tie with c1), and the fleet-wide and one-vessel questions of amendment 2.
- **Deviations:** A1 became the Voyages panel (owner); the watch makes the advice itself (owner, amendment 1); the
  supervisor's fold, the `arrival` route to `watch_alerts` and the sign rule on the watch's rows were added after the
  real probe (owner, amendment 2); the time-limited picomatch exception (owner, staging plan D-S-9).
- **Known limits:** one advice of the real run ended `validation_failed` (vessel 157, recorded with its reason); a broad
  "which vessels" answer may give the count and not every name.

---

**Approved 2026-11-17** — written PROPOSED the same day on the owner's request ("أيوه، اكتبها"). The
owner took A1–A5 by clickable answers, revised A1 to Voyages, and then set the order (A6): "تنفذ الـ feature دي الأول
وتعملها test، بعديها ابقى اشتغل على staging". So this plan runs **before** the staging readiness plan (APPROVED
2026-11-17, its own session), which waits; the staging session was told which files this plan touches. Claude runs
no git command; the one commit is the owner's.

## 1. Goal

Make Just-in-Time arrival advice (ADR-070), today reachable only from the CLI `Arrival_advice.py` and from Ask (the
supervisor's `arrival_advice` tool), a **first-class product in the web**:
- it opens in **one click from the alert that calls for it** (`jit` / `rta_late` on Voyages);
- it lives **inside Voyages**, beside the watch that raises those alerts, without merging any graph.

## 2. What exists today (inspected 2026-11-17)

| Piece | State |
|---|---|
| Graph `pipelines/agents/graphs/arrival_advice.py` (code options keep / jit / floor / catch_up / cape, one `writer` call with slots, a code Validator; threads `arrival_advice:<emp>:<date>:<vessel>:<n>`) | EXISTS (ADR-070) |
| CLI `pipelines/scripts/agents/Arrival_advice.py`, check `Arrival_advice_check.py` Phases 1–8 | EXISTS |
| Supervisor tool `arrival_advice` (JIT words only) — so Ask already answers "what speed to make the berth time?" | EXISTS |
| Voyage watch `jit` / `rta_late` alerts (`voyage_watch.py`: `rta_utc`, `rta_location`, `wait_h` / `late_h`, `jit_option`, `jit_speed_kn`, `catch_up_speed_kn`, fuel change) | EXISTS in code; **no saved run carries them yet** (the three runs in `reports/voyage_watch/` predate JIT) |
| API endpoint for arrival advice | **MISSING** (only `/route-advice` + `/voyage-watch/*` in `routers/operations.py`) |
| `result_summary` number spans for receipts (as route advice has, D-FE-1) | **MISSING** |
| `/me` product flag | **MISSING** (`products` has `route_advice`, `voyage_watch`) |
| Web page / form | **MISSING**; Voyages shows a `jit` / `rta_late` alert with its raw kind and a generic icon (`VoyageWatch.tsx` `KIND` map: weather / suez_traffic / customer), no action |
| `WatchAlert.kind` description in `schemas.py` | stale ("weather \| suez_traffic \| customer") |

## 3. Design — a separate graph, joined to the voyage watch in the interface (owner, A1 revised)

The two products answer different questions:

| | Route advice (ADR-057) | Arrival advice (ADR-070) |
|---|---|---|
| Question | Suez or the Cape for this voyage? | Which speed to make the port's requested time? |
| When | Planning, also a hypothetical vessel | A vessel of ours at sea |
| Inputs | origin, destination, vessel or type / SCNT, speed | vessel, RTA (port message or typed), location |
| Output | two route costs and the difference | keep / jit / floor / catch_up / cape with times, waits, fuel |
| Validator | the cost rule | sign and RTA-label rules |

Merging them would put both rule sets in one Validator, and each form would carry fields that half of its questions
never use. So the graphs stay apart: **two graphs and two endpoints**.

In the interface, arrival advice belongs with the **voyage watch**, not with route advice:
- it covers the same vessels at sea, the same clock and the same RTA data;
- the watch already calls `arrival.options` to raise `jit` / `rta_late` (the same arithmetic).

It stays a separate graph from the watch too. The watch is fleet-wide and scheduled, with code per vessel and one
brief. The advice is one vessel on demand, with a `writer` call and its own Validator. Putting the advice inside the
watch would spend a model call per vessel, against the 500 free requests a day.

1. **Voyages → one click.** A `jit` or `rta_late` alert gets the label "Arrival timing" with a clock icon, and an
   **"Advise arrival"** action. The action opens the advice in an **arrival panel inside Voyages**, prefilled with
   the vessel and the alert's RTA and location. The alert says something is wrong; the advice says what to do.
2. **Any vessel at sea in the run's ETA table** also gets "Advise arrival". In the same panel, the RTA is optional
   (empty = the RTA the port sent, known at the clock), and the location is berth or pilot boarding place. The
   earlier arrival advice is listed on Voyages, each with its own URL.
3. **The two products link to each other.** An arrival advice whose options include `cape` shows **"Compare routes"**,
   which opens route choice for the same vessel and destination.
4. **Ask is unchanged.** It already routes JIT words to the same graph.

## 4. Owner decisions (to take in one round, clickable)

| # | Question | Recommended | Alternative |
|---|---|---|---|
| A1 | Where the form lives | ~~A tab "Arrival timing" in Routes~~ → **an arrival panel inside Voyages** (owner, revised 2026-11-17) | Its own page `/arrivals` in the menu |
| A2 | The alert action | "Advise arrival" on `jit` / `rta_late`, prefilled | Only a link to the empty form |
| A3 | Who may use it | A new `/me` flag `arrival_advice`, the same access as the graph's tools (ADR-006: AIS, ports, vessels, vessel params, port-call messages) | Reuse `route_advice` |
| A4 | Saved runs with JIT alerts | The owner re-runs the watch at the clock once (a new run `…T0000Z_2`), so Voyages shows them | Wait for the next scheduled run (the replay clock is at its end, so it may not come) |
| A5 | Proof on real models | One advice from a real `jit` alert + one typed RTA, on the real API | Fake-roles only |
| A6 | Timing | ~~After the staging plan closes~~ → **first, then staging** (owner, 2026-11-17) | Now, alongside it |

## 5. Phases

**P1 — API** (`pipelines/api/routers/operations.py`, `schemas.py`, `me.py`)
- `POST /arrival-advice` returns 202 with a run + SSE (the run executor, a thread lock, audit, tracing), as
  `/route-advice` does.
- `GET /arrival-advice` lists the asker's threads; the CEO sees all.
- `GET /arrival-advice/{thread}`: the owner or the CEO, else 404.
- Every response is typed. `result_summary` gains number spans for receipts, re-rendered from the slots with no check
  changed (D-FE-1). `/me` gets `products.arrival_advice` (A3). The `WatchAlert.kind` description is corrected.
- Then regenerate the OpenAPI snapshot, the BFF allow-list and the Orval client.
- `Api_check.py` gets a new phase: run → events → detail, the refusal matrix, and another employee's thread → 404.

**P2 — Web** (`web/src/components/voyages/`, a detail route under `/voyages/arrival/[thread]`)
- Voyages gets the arrival panel, A1. `ArrivalPanel`:
  - the form;
  - the live steps;
  - an options table (option, speed, arrival, wait / late, fuel t / SDR, change), with the recommended option marked
    and the numbers as receipt chips;
  - reasons, risks and assumptions as plain text;
  - "Compare routes" when there is a `cape` option;
  - the earlier advice, with a detail URL.
- `VoyageWatch.tsx`: `KIND` gains `jit` / `rta_late` (A2). "Advise arrival" sits on those alerts and on each
  in-transit row of the ETA table; the prefill goes in the URL, so a reload keeps it.
- English UI; model text in `dir="auto"` blocks; no computing in the browser.

**P3 — Tests**
- Mocked E2E (desktop + mobile): the form, receipts, an Arabic reason rendered RTL, the alert → prefilled advice, the
  cape link, axe 0 serious / critical. `npm run check` ✅.
- The stack suite (`web/tests/stack/`): the endpoint's access matrix and leakage 0. The scripted model cannot write, so
  the advice ends calmly as `output_invalid`, with the code options shown if the graph keeps them. Check that first.
  Otherwise assert only the calm failure.

**P4 — Real run (owner, A4 / A5)**
- Re-run the watch at the clock:

  ```powershell
  uv run python pipelines/scripts/agents/Voyage_watch.py run --as <employee> --as-of 2026-09-13T00:00
  ```

  Then confirm Voyages shows the `jit` / `rta_late` alerts (ADR-070 counted 41 at the clock).
- From one alert, run the advice on the real models and confirm it passes the Validator.

**P5 — Records:** ADR-070 amendment (the web and API surface), ADR-060 note, ARCHITECTURE (the web row + the
operations endpoints), THREAT_MODEL (the new endpoint in the access row), ROADMAP; archive.

## 6. Done when

- `POST / GET /arrival-advice` typed, in OpenAPI, the allow-list and the client; `Api_check` with the new phase ✅.
- Voyages has the arrival panel; a `jit` / `rta_late` alert, or a vessel in transit, opens a prefilled advice in
  one click; an advice with a `cape` option links to route choice on Routes.
- The mocked E2E and the stack suite ✅ (leakage 0); `npm run check` ✅; lint ratchet 0.
- The owner's real run: Voyages shows JIT alerts, and one advice from an alert passes on the real models.
- ADRs, ARCHITECTURE, THREAT_MODEL and ROADMAP updated; plan archived; the commit is the owner's.

## 7. Risks

| Risk | Mitigation |
|---|---|
| No saved run has JIT alerts, so the one-click entry cannot be seen | A4: one owner re-run at the clock; the mock covers the UI meanwhile |
| The staging plan edits the same API / compose files | A6: start after it closes; if run alongside, touch only the files named in P1–P2 |
| A new endpoint widens the attack surface | The same run executor, owner / CEO read rule, audit and allow-list as route advice; the stack suite proves the matrix |
| The writer's text claims a time is the RTA | ADR-070's RTA-label Validator rule already refuses it; the web shows only validated text |

## Progress / deviations

- 2026-11-17 — written PROPOSED; waiting for A1–A6 and the owner's approval.
- 2026-11-17 — **owner decisions (clickable, the recommended option each time):**
  - A1: the "Arrival timing" tab in Routes.
  - A2: the "Advise arrival" action on `jit` / `rta_late`, prefilled.
  - A3: a new `/me` flag `arrival_advice` from the graph's tool access.
  - A4 + A5: the owner re-runs the watch at the clock, then one advice from an alert on the real models.

  A6 (timing) is not answered yet; the plan stays PROPOSED until it is.
- 2026-11-17 — **A1 revised by the owner:** asked whether to merge with route advice or with the voyage watch, the
  owner chose the arrival panel **inside Voyages**. The interface joins the watch; the graphs stay separate (§3).
  §1, §3, P2 and the done-when were updated.
- 2026-11-17 — **A6 and approval:** the owner put this plan first, staging after it. Status: APPROVED.
- 2026-11-17 — **Design revised by the owner (clickable):** "متبصش ع عدد الـ calls … أفضل وأدق شكل للـ merge" → **the
  watch makes the advice** (a new `arrival` node: every `jit` / `rta_late` vessel advised in the same run, at the same
  clock and RTA, saved in the run file before the brief) **+ on demand** for any vessel at sea. ADR-070 amendment 1.
- 2026-11-17 — **P1–P3 done.**
  - **API:** `operations.py` serves `POST /arrival-advice` (a run, a 403 up front), `GET /arrival-advice` and
    `GET /arrival-advice/{thread}`; `result_summary` gains number spans; `/me` gets `products.arrival_advice`; the
    alert reader attaches `advice` to its own alert (`schemas.WatchAlert.advice`, `ArrivalAdvice`,
    `ArrivalAdviceDetail`). OpenAPI 40 paths; allow-list and Orval regenerated.
  - **Watch:** `voyage_watch.advise_arrivals` + the `arrival` node (`build_graph(..., arrival_advice=True)` from the
    CLI / scheduler), `VoyageWatchResult.arrivals`.
  - **Web:**
    - new files `src/components/voyages/Arrival.tsx` (`AdviceCard`, `ArrivalRequest`) and `ArrivalDetail.tsx`, the
      page `/voyages/arrival/[thread]`, and `src/lib/arrival-advice.ts`;
    - Voyages: the alert kinds "Arrival timing" / "Late for the requested time", the advice inline under its alert,
      "Advise arrival" on the ETA board;
    - Routes takes `?vessel=&destination=` (checked server-side) for "Compare routes".
  - **Checks:**
    - `Api_check` 12 / 12 (Phase 8 + arrival);
    - `Arrival_advice_check` Phases 1–7 + **6w** (41 alerted vessels advised, and the advice = the alert on all 41);
    - `Voyage_watch_check` 1–7 unchanged;
    - `npm run check` ✅ (3 new voyages tests + 1 routes test);
    - the stack suite **17 / 17** (one arrival test on the real API: the asker's page and list, 404 for another
      employee);
    - lint 0.
  - **Deviations:** the arrival tab of A1 became the Voyages panel (owner). The advice in the watch also serves rows
    without a written part: code-only `late` / `on_time` cases show the code headline.
  - **Next (P4):** restart the API and rebuild the web with the new code, re-run the watch at the clock on the real
    models (the run file then carries `arrivals`), and one on-demand advice on the real models.
- 2026-11-17 — **P4 done** (ADR-070 amendment 1, "Real run"): the watch at the clock (`voyage_watch:20260913T0000Z:2`)
  and one on-demand advice on the real models.
- 2026-11-18 — **resumed after a power cut** (2026-11-17 16:01, during the last regression round). Re-run on the
  current code: `Voyage_watch_check` ✅ (the first re-run failed in Phase 7 on a check thread the cut left behind; that
  run deleted it and the next passed unchanged), `Arrival_advice_check` Phases 1–7 ✅, the stack suite **17 / 17**,
  full-data `Api_check` **12 / 12**.
- 2026-11-18 — **owner decision: the large "alerts" request is fixed now, before staging.** `supervisor.fold_arrival_rows`
  (model view only): more than 4 arrival rows → the 4 most urgent + `arrival/jit` and `arrival/rta_late` totals computed
  in code; customers cut to 5 + `customer/others`. On the JIT run the tool result falls from 80 rows / 8.8 k est tokens
  to 25 rows / 3.2 k. The frozen run (no arrival rows) is returned untouched. Checks on fake models: `Supervisor_check`
  (new Phase 2 block), `Supervisor_tools_check`, `Stage2_eval` Phases 1–3, lint 0, `npm run check` ✅.
- 2026-11-18 — **real-model measurement done** (owner's go-ahead): ADR-070 amendment 2. `stage2_eval_2026-11-18_fold1.json`
  every gate met, ADR-052 tie against c1; the largest broad request 6,990 input tokens. Probe threads
  `ask:12:20260913T0000Z:18…23`: 4 of 6 right (checked against the run file), 2 wrong `not_in_data`.
- 2026-11-18 — **owner: fix the router gap.** The `arrival` rule also offers `watch_alerts`, and the sign rule covers the
  watch's rows (amendment 2). Re-asked on the real models: threads `ask:12:20260913T0000Z:24…27`, all answered from the
  right tool with 0 problems. Plan closed; the staging plan resumes.
