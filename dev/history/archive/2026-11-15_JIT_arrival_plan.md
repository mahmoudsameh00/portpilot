# Plan — Just-in-Time Arrival advice: a third Operations product

## Implementation record — Status: IMPLEMENTED (2026-11-15)

Approved and implemented the same day in one session (the owner, through the session that started it: "do it now";
J1–J7 answered in one round, §2a). Lasting decision: **ADR-070** (+ notes on ADR-058 and ADR-059).

**Built:** migration 030 `public.port_call_messages` (applied on the owner's yes; dry run rolled back
first; snapshot +148 lines, insertion only; `db/audit/2026-11-15_after_030_report.txt` 0 errors, new §29 =
680 | 500 | 25 | 155 | 0 | 0 | 0 | t | f | f) filled by `pipelines/scripts/synthetic/Port_call_generator.py` (680
messages from the declared schedule, seed 42; checkpoint `pipelines/checkpoints/synthetic/Port_call_generator.md`);
`pipelines/agents/tools/arrival.py` (the RTA known at the clock, the options, D-J8's two text rules); the graph
`pipelines/agents/graphs/arrival_advice.py` + models + the skill `arrival-advice` (`reviewed_by_owner: no`); the CLI
`pipelines/scripts/agents/Arrival_advice.py` (`ask` / `rta` / `show` / `list`; smoke: vessel 28 as employee 13 → ok,
jit 9.49 kn); the supervisor's product tool + router rule; the voyage watch's `rta_late` / `jit` alerts; the 30-day
retention of the new threads (`scheduling.describe_arrival_advice`, `Weekly_pack.py prune`, every scheduled firing);
`deck/slots.py` (`arrival.` ids). Docs: `ARCHITECTURE.md` (§1, §2, §4, §7, §9), `docs/ROADMAP.md`, `docs/DATA_MAP.md`,
`docs/rbac_mapping.md`, `db/README.md`, `docs/CHECKPOINT_agents_stage2.md`, `docs/archive/README.md`.

**Results — `Arrival_advice_check.py` Phases 1–8 ✅** (checkpoint `pipelines/checkpoints/agents/Arrival_advice_check.md`):
the store = the CSV and the clock rule (120 probes); 20 frozen cases = an independent computation (20 / 20 planted
result errors); 400 grid cases, 0 property violations; the Validator 60 / 60 planted text errors, 0 false alarms;
the graph on fake models on every path; the watch's 41 arrival alerts = the independent computation; 0 / 57 golden
items re-routed; **real model 8 / 8 advices pass the Validator, each = the rule**; two supervisor questions (EN + AR)
answered from the tool; the watch brief over arrival alerts passed. ≈ 14 fresh flash-lite calls (+ 2 probe calls).
**Regressions ✅:** `Supervisor_check`, `Supervisor_tools_check` (union 15), `Stage2_eval` Phases 1–3 (0 calls),
`Stage2_tools_check`, `Tools_check`, `Scheduler_check` 6 / 6, `Voyage_watch_check` Phases 1–7 + 4s (D-J7),
`Route_advice_check`, lint ratchet ruff 0 / pyright 0.

**Deviations:** D-J1…D-J8 in §7 (the RTA store; no CO₂; the watch's alerts; `registry.ARRIVAL_ADVICE` beside
`route_advice` instead of `PRODUCTS`; no hypothetical vessel; the S2 golden set kept frozen (v2) instead of a v3;
the watch check's fixtures; the sign / RTA-label rules from the first real run). **Not done:** an API route (the
plan's "later"); the voyage-watch-brief skill text for the new alerts (owner-reviewed, unchanged). **Open (owner):**
the review of the skill `arrival-advice`; the commit when every plan in `docs/plans/` is closed;.

**Status: IMPLEMENTED (2026-11-15)** (approved the same day) — the owner answered J1–J7 in one round (§2a); J6 and the CO₂ question changed
the design (§2a, D-J1…D-J3). Written 2026-11-08 on the owner's request: a ChatGPT answer the owner shared suggested
"Vessel Speed Optimization / Just-in-Time (JIT) Arrival" ("synchronizing vessel arrival with port capacity"), and
the owner chose "write a separate proposal".
**Order:** it does not touch the weekly pack. It can run after, or alongside, `Pack_external_context_plan.md`
(APPROVED, in progress) and `Traffic_billing_link_plan.md` (PROPOSED). The owner chooses the order (J7).
`docs/plans/` also holds `Frontend_plan.md` (another session).
Touches ADR-055 (Stage 2 tools, the clock `as_of`), ADR-056 (no live AIS), ADR-057 (`route_advice`: code computes,
one writer call with slots, a code Validator), ADR-058 (`voyage_watch`, ETA rule R), ADR-059 (the supervisor,
`registry.PRODUCTS`), ADR-064 (API).

## 0. The idea, and what is already in the project (existing, verified 2026-11-08)

**JIT arrival:** a vessel that would arrive before its berth is ready sails slower, so it arrives when the port
can take it, instead of racing and then waiting at anchor. It saves fuel, emissions and anchorage congestion. In
real ports the berth time comes as a **Requested Time of Arrival (RTA)** from the port or the agent.

**Already built (Stage 2), which JIT reuses as is:**
- `voyage_status`: the vessel's position at the clock and the distance left on its route.
- `eta.eta_rule` (rule R): ETA at the recent speed plus the harbour approach (10 nm at 6.7 kn).
- `vessel_params`: fuel per sea day at **any** speed by the cube law (main × (v / v_ref)³ + aux) and the dated SDR
  price per tonne.
- `sea_route` + `route_advice`: Suez vs Cape distances and costs, Suez dues by `compute_toll`.
- `marine_weather` and the watch's alert rules.

**Missing:** any data on port readiness. The project has no berth schedule, no port waiting times and no RTA
(checked in `ARCHITECTURE.md` and `docs/DATA_MAP.md`). Also, the synthetic voyages sail at a constant speed and pass
intermediate ports without stopping (ADR-058 F2 / F7).

## 1. Why the code can answer it (the arithmetic, before any design)

- Fuel per **day** grows with v³ and the **days** of a leg fall with 1 / v, so the main engine's fuel per **leg**
  grows with **v²**. Slowing from 14 to 12 kn uses (12 / 14)² ≈ 73 % of the main-engine fuel for that leg (≈ 27 %
  less). The auxiliaries burn per day, so the longer voyage gives part of it back. The code counts both.
- **The option it is compared with** = "sail at service speed, then wait": the leg at service speed plus the hours
  at anchor × the auxiliaries' fuel per day.
- **The ChatGPT example (go round the Cape to arrive later) checked with the project's own numbers:** Singapore →
  Rotterdam is 8,388.5 nm via Suez. At 14 kn that is 24.97 days; at 10 kn it is 34.95 days. Slowing down alone
  absorbs **about 10 days** of delay, and burns only (10 / 14)² ≈ 51 % of the main-engine fuel. The Cape adds
  3,488 nm of steaming. So a diversion only to arrive later is almost never the cheaper choice. It is worth looking
  at only when the delay is longer than slow steaming can absorb, or when Suez is closed or risky (that case is
  already `route_advice`'s). The product reports this comparison with numbers instead of assuming it.

## 2. Owner decisions (asked once, as clickable choices, recommendation first)

| # | Question | Recommended | Alternatives |
|---|---|---|---|
| J1 | Where the port's ready time comes from | **The RTA as an input** (in the question, the API or the CLI, like the real RTA message): no new data | (b) A synthetic berth schedule per port call (a new generator + migration), so the watch can run JIT for the whole fleet every 12 h. (c) IMF PortWatch daily port activity as a congestion proxy: a signal, not a berth time |
| J2 | Lowest speed allowed | **max(8 kn, 50 % of the band's IMO reference speed)**, stored with its source and shown as an assumption | A value per vessel type set by the owner / no floor |
| J3 | Safety margin before the RTA | **2 h** (arrive at RTA − 2 h, so a small delay does not miss the berth) | 0 h / a value given in the question |
| J4 | The Cape option | **Computed only when the delay cannot be absorbed at the lowest speed via Suez** (through `route_advice`'s code), with the numbers either way | Always shown / never |
| J5 | The model's role | **The same pattern as ADR-057: code computes everything, one `writer` call with number slots, a code Validator** (the recommendation = the cheapest feasible option, unless a cited risk justifies another) | No LLM: a code template only |
| J6 | Where it runs | **A new graph `arrival_advice` + a product tool in `registry.PRODUCTS` (the supervisor) + a CLI `Arrival_advice.py`** | Also inside `voyage_watch` (needs J1 = b) |
| J7 | Order | **After `Traffic_billing_link_plan.md`** (one plan at a time, one commit per plan) | Before it / in parallel in its own session |

### 2a. The owner's answers (2026-11-15, one round of clickable choices)

| # | Answer |
|---|---|
| J1 | The RTA as an input (recommended) — and, through J6, also a stored RTA message (D-J1) |
| J2 | max(8 kn, 50 % of the band's IMO reference speed `vessel_performance.ref_speed_kn`) (recommended) |
| J3 | 2 h (recommended) |
| J4 | The Cape only when the delay cannot be absorbed at the floor via Suez (recommended) |
| J5 | The ADR-057 pattern: code computes, one `writer` call with slots, a code Validator (recommended) |
| J6 | **Also inside `voyage_watch`** (not the recommendation) — with J1 = input, the owner then asked for "a simulation of reality that is dynamic and real, so that on real data nothing needs changing", and left the design to the assistant → D-J1 |
| J7 | Now, in its own session (the owner, through the session that started this one) |
| CO₂ | **No CO₂** (not the recommendation): the table reports fuel in tonnes and SDR only; no emission factor, no migration for it (D-J2) |
| Skill | `arrival-advice` written by the assistant, reviewed by the owner at the end (recommended) |
| Migration 030 | Approved, applied (the owner's answer to D-J1's question) |

- **D-J1 — the RTA store (the assistant's design, approved with migration 030).** A real RTA is a port-call
  message (IMO's *Just In Time Arrival Guide*, IHO S-211 / DCSA JIT port-call timestamps): who sent it, when, for
  which vessel, port call and location, and later revisions or a cancellation. So: a table
  `public.port_call_messages` (migration 030), one row per message (vessel, port UN/LOCODE, voyage number, time type
  `RTA`, location `berth` or `pilot_boarding_place`, the requested time, `sent_at`, `message_status` requested /
  cancelled, `real_or_synthetic`, sender, source). **The RTA known at the clock** = the latest message with
  `sent_at <= as_of` for the vessel's current port call; a cancelled latest message = no RTA. Today it is filled by
  a synthetic generator (`pipelines/scripts/synthetic/Port_call_generator.py`, seed 42), which draws the port's
  berth plan from the vessel's **declared schedule** (departure + route / service speed — what a port knows), never
  from the voyage file's true arrival (the ETA answer key, P9-7); real messages later are rows with
  `real_or_synthetic = 'real'`, read by the same code. A question (CLI, supervisor) may still give its own RTA
  (J1), which wins over the stored one and is said so.
- **D-J2 — no CO₂:** the plan's CO₂ column is dropped (owner); a CO₂ factor table can come later as its own
  migration without touching the option arithmetic.
- **D-J3 — the watch (J6):** a code step after the ETAs: for each vessel at sea with an RTA known at the clock, the
  same arrival arithmetic (no Cape, no model) → alerts `<vessel>/rta_late` (R arrives after RTA − 2 h; high when
  ≥ 12 h late) and `<vessel>/jit` (moderate: at the current speed it would wait ≥ 6 h, and a slower speed ≥ the
  floor saves fuel). The brief may cite them; anchored vessels show their RTA in the ETA table.

## 3. Design (APPROVED 2026-11-15; with §2a)

### 3a. Inputs (code)
`vessel_id` (or type + SCNT), destination port (UN/LOCODE), RTA (UTC), and the clock `as_of` in the run context
(ADR-055 (2)). From the tools: position and distance left (`voyage_status`), ETA at the current speed (rule R),
fuel per day at any speed and the SDR price (`vessel_params`).

### 3b. Options (code; Decimal, rounded once)
1. **Keep speed, then wait:** arrival = rule R; waiting hours = (RTA − 2 h) − arrival, if positive; fuel = the leg
   at the current speed + waiting hours × auxiliaries per hour.
2. **JIT speed:** v = open-sea distance ÷ (hours to RTA − 2 h − approach hours); if v < the floor (J2) → "cannot
   absorb at the lowest speed", else fuel = the leg at v.
3. **Cape** (J4, only when 2 is infeasible): `route_advice`'s numbers for the Cape route at the speed that fits the
   RTA, Suez dues saved included.
4. **Already late** (ETA after the RTA): no slowing down; report the delay in hours and the speed needed to catch
   up, capped at service speed.
- The output table per option: speed, arrival time, hours waiting, fuel t, fuel SDR, CO₂ t (the fuel's IMO factor,
  stored in the database with its source, not in the code), and the difference vs option 1.

### 3c. Writer + Validator + render
- One `writer` call: a recommendation with slots and cited evidence ids, the same contract as `route_advice`.
- **Validator:** every number a slot; the recommendation = the cheapest feasible option, unless the first reason
  cites a risk with evidence (a weather alert on the remaining route, or Suez traffic ≤ −20 %).
- The code writes the assumptions: constant speed, the cube law, the floor, the margin, port time not modelled.

### 3d. Product
- Graph `pipelines/agents/graphs/arrival_advice.py` (PostgresSaver, one thread per question).
- Skill `arrival-advice` (reviewed by the owner).
- A product tool `arrival_advice` in `registry.PRODUCTS`, so the supervisor answers "vessel 21 has a berth at
  Rotterdam on 12 June 14:00: what speed?". RBAC: Operations.
- CLI `pipelines/scripts/agents/Arrival_advice.py`. An API route later, in the API phase's style (ADR-064).

### 3e. Evaluation — `pipelines/scripts/agents/Arrival_advice_check.py`
1. **Hand-check:** 20 cases (early, on time, late, infeasible → Cape, Suez-only ports) = an independent computation.
2. **Planted errors** in the code results and in model text: all caught by the Validator.
3. **Property checks:** fuel(JIT) ≤ fuel(keep + wait) whenever JIT is feasible; arrival(JIT) = RTA − 2 h within
   rounding.
4. **The real model:** 8 / 8 recommendations pass the Validator (the ADR-057 bar).

**Done when:** all four parts pass; the supervisor golden set gets JIT questions (it becomes v2, frozen); no
regression on the Stage 2 baseline (ADR-059).

## 4. Out of scope
- A real berth or port-call system, live AIS (ADR-056), and port-side optimisation (berth allocation for many
  vessels at once).
- Charter-party clauses (who pays for waiting vs slow steaming): reported as an assumption only.
- Weather-routing (changing the path for weather): weather stays a risk flag, as in the watch.

## 5. Risks
- **J1 = RTA as input** means the product is only as good as the RTA it is given. That is honest and realistic, but
  the watch cannot use it fleet-wide until J1 (b) exists.
- **Synthetic speeds are constant**, so ETA accuracy here says the code reads the data correctly, not that it would
  be this accurate at sea (the same caveat as ADR-058).
- **The cube law is an approximation at very low speeds:** hence the floor (J2), shown as an assumption.

## 6. Files (planned)
`pipelines/agents/graphs/arrival_advice.py` · `pipelines/agents/skills/arrival-advice/SKILL.md` ·
`pipelines/agents/graphs/models.py` (request / advice models) · `pipelines/agents/tools/registry.py`
(`registry.PRODUCTS`) · `pipelines/scripts/agents/Arrival_advice.py` · `pipelines/scripts/agents/Arrival_advice_check.py` ·
a migration only for the CO₂ factor table (or a column in `bunker_prices`) · `ARCHITECTURE.md` · `docs/ROADMAP.md` ·
`docs/decisions.md` (a new ADR at close) · `docs/CHECKPOINT_agents_stage2.md` (a section).

## 7. Progress / deviations

**Handoff (2026-11-15, one session):** approved → migration 030 written by the generator, dry-run (rolled back),
applied, snapshot refreshed (+148 lines, insertion only), audit §29 = expected → `tools/arrival.py`, the graph, the
skill, the CLI, the retention, the watch's RTA alerts, the supervisor's tool and rule → `Arrival_advice_check.py`
(Phases 1–7 fake, 8 real) → the regressions. Nothing committed (owner rule: one commit when every plan is closed).

- **D-J1** (design, §2a): the RTA store `port_call_messages` + the generator from the declared schedule.
- **D-J2** (owner): no CO₂ — the option table has no CO₂ column, no factor table.
- **D-J3** (J6): the watch's arrival alerts `rta_late` / `jit`; thresholds fixed before any measurement: JIT when the
  vessel would wait ≥ 6 h, late high from 12 h.
- **D-J4:** the plan said "a product tool in `registry.PRODUCTS`"; `PRODUCTS` holds tools whose function takes
  `(user, **args)` (the RBAC matrix of `Supervisor_tools_check.py` calls them so). Like `route_advice` (P12-2), the
  arrival graph needs the roles → `registry.ARRIVAL_ADVICE` + `products.make_arrival_advice_tool`, bound in
  `supervisor_tools` (the union 14 → 15).
- **D-J5:** §3a's "or type + SCNT" (a hypothetical vessel) dropped: an arrival needs a position and a distance left,
  which only our vessels at sea have. A question about another port than the voyage's destination →
  `not_destination` (intermediate ports are passed without a stop, F2).
- **D-J6:** §3e's "the supervisor golden set gets JIT questions (it becomes v2, frozen)": the S2 golden set is
  already v2 (57 items, the Stage 2 baseline). Adding items would make it v3 and need a new baseline (two full real
  runs, ≈ 300 calls). Kept frozen instead; the supervisor's JIT path is checked by `Arrival_advice_check.py` Phase 7
  (router, the tool's rows, the answer check) and Phase 8 (two real questions, EN + AR). No regression by
  construction: 0 of the 57 golden questions match the new router rule (the first draft's "what speed" matched o08
  "At what speed is vessel 12 sailing…" and was narrowed to "what speed should / to"), and no prompt constant changed
  (`SUP_TASK`, `ANSWER_TASK`, `SLOT_RULES`; the row keys of the new tool travel in its own note).
- **D-J7:** the watch's existing checks: `Voyage_watch_check.py` Phase 4's clean brief (a fixture) now also cites the
  arrival alerts (4 high `rta_late` at the clock); its reviewed counts of the live run (Phase 6) gained the arrival
  alerts; `Supervisor_tools_check.py`'s union 14 → 15.
- **D-J8 (found by the first real run, Phase 8):** all 8 advices passed, but two texts wrote "saving −123.0 t" /
  "saving −160.5 t" (a `change_*` slot writes its own sign → a double negative after "save"), one in the watch brief
  too; and the two supervisor answers called the JIT arrival time (RTA − 2 h, `target_utc`) "the RTA". Fixes, in
  code: `arrival.sign_problems` (a change slot — `change_*` or `rule_change_*` — right after save / reduce / يوفر /
  يقلل → a problem, one patch) and `arrival.rta_label_problems` (a date-time right after "RTA / requested time /
  الميعاد المطلوب" must be the RTA) in the arrival Validator, the sign rule in the watch brief's Validator, and both in
  the supervisor's answer check **only when the arrival tool is in the evidence** (no golden item has it, so no
  Stage 2 answer is touched); the product tool's note says which field is the RTA. The second real run still showed
  "saving −123.0 t" (a `rule_change_fuel_t` slot the first pattern missed) and the Arabic answer naming the target
  "الميعاد المطلوب" → the pattern widened and the label rule added; Phase 4 gained two plants per case (60 / 60), Phase
  7 two refused supervisor answers. Not changed:
  the owner-reviewed skill `voyage-watch-brief` (it does not describe the arrival alerts; the real brief cited them
  correctly anyway) — a wording line there is the owner's call.
