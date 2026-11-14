# Plan — Just-in-Time Arrival advice: a third Operations product

**Status: PROPOSED (2026-11-08)** — written on the owner's request: a ChatGPT answer the owner shared suggested
"Vessel Speed Optimization / Just-in-Time (JIT) Arrival" ("synchronizing vessel arrival with port capacity"), and
the owner chose "write a separate proposal". No code before the owner approves this plan.
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

## 3. Design (PROPOSED; assumes the recommended answers)

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

(empty: not approved yet)
