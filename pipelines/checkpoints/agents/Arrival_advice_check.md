# Final Checkpoint — Arrival_advice_check (JIT arrival plan, 2026-11-15)

**What it proves:** Just-in-Time arrival (ADR-070) reads the port's Requested Time of Arrival the way real data comes
(the latest port-call message sent at or before the clock), computes every option in code (= an independent
computation), lets the model only choose and explain through number slots, refuses every planted wrong number and
every choice that breaks the rule, survives a crash, adds the right arrival alerts to the voyage watch, and is reached
by the supervisor only for JIT questions. Design: plan §2a (owner answers J1–J7, D-J1…D-J3), the skill
`arrival-advice` (owner review pending).

| Phase | Step | Result (2026-11-15) |
|---|---|---|
| 1 | The RTA store | the table = the generator's CSV (680 rows); 120 clock probes (before the first message, at it, just before / at a revision or a cancellation) = the independent rule; every first RTA inside its scenario's range around the **schedule**; a probe user refused; 44 of the 219 vessels at sea have an RTA at the clock |
| 2 | 20 frozen cases (`arrival_cases.json`) = an independent float computation from the reference CSVs | options, speeds, times, waits, fuel t, SDR and the rule's choice agree on all 38 options (rules: jit 10, keep 5, floor 3, catch_up 1, cape 1); 20 / 20 planted result errors caught |
| 3 | Properties on 400 grid cases (40 vessels × 10 RTA offsets, 696 options) | 0 violations: JIT fuel ≤ keep, JIT at the target (within the speed's rounding), the floor, the rule = the cheapest on-time option, wait / late exclusive, waiting monotone in the RTA, the Cape only with the floor |
| 4 | The Validator | 60 / 60 planted errors in model text (typed numbers, a foreign date, unknown / uncited evidence, a non-rule or non-computed option, unknown field / row key, a number in a risk, a change slot after "saves", an arrival time named as the RTA); 0 false alarms on 20 good advices; overrides: a storm row and Suez −25 % pass, no row and −10 % refused |
| 4s | The skill | 1,166 tokens (≤ 1,200), 207-char description, 11 example slots render |
| 5 | The graph on FakeRoles + PostgresSaver (mock Open-Meteo / PortWatch) | 20 cases: 16 ok (1 call each, recommendation = the rule), 2 on_time + 2 late with no call; patch, validation_failed, output_invalid; not_at_sea, not_destination, no_rta, not_permitted; weather down → "context unavailable"; a storm → the justified `keep`; crash + resume with 0 HTTP repeated; 30 check threads deleted |
| 6 | The watch (D-J3) | 41 arrival alerts at the clock (24 jit, 17 rta_late, 4 high) = the independent computation; 75 anchored vessels show their RTA; the brief Validator passes a cited brief, refuses a typed number and a foreign date; a week earlier no message sent after that clock is read |
| 7 | The supervisor | 5 / 5 JIT questions (EN + AR) routed to `arrival_advice`; 0 / 57 golden items re-routed; refused to a probe user; the product tool's rows keyed by option + summary + advice; the answer check binds its slots and refuses a double negative and a wrong RTA (only when the arrival tool is cited) |
| 8 | The real model (`writer` = flash-lite; the supervisor on the `tools` role) | **8 / 8 advices pass the Validator**, every recommendation = the rule (6 jit, 2 floor); first run 16 calls, 7 patches; re-runs cached. Two supervisor questions answered (EN 3 calls, AR 4 calls), both citing `arrival_advice`. The watch brief over 6 arrival alerts of 6 vessels passed. ≈ 14 fresh flash-lite calls in all (+ 2 probe calls before) |

## Problems and fixes
1. **The skill was over the loader's budgets** (description 270 > 250 chars, body 1,598 > 1,200 tokens) — every
   other check failed on load (the loader validates the whole catalogue) → shortened, the rules kept.
2. **The router's "what speed" matched golden item o08** ("At what speed is vessel 12 sailing for its ETA…") → the
   rule narrowed to "what / which speed should / to"; the check asserts 0 golden items re-routed.
3. **A Cape case was not a Cape case** (R + 20 days was absorbable at the floor for a fast vessel) → the case's RTA
   = the last fix + the distance left at 8 kn + 5 days (the floor surely waits).
4. **5 of 20 planted SDR errors slipped** (a tolerance of 0.2 t × the price ≈ 145 SDR) → money is checked exactly as
   the option's own tonnes × the reference price, and fuel tonnes against the independent value.
5. **A week-earlier clock had vessels with no AIS fix yet** → only vessels with a status at that clock are probed.
6. **The real texts passed but read wrong (D-J8):** "saving −123.0 t" (a change slot after "save"), the same in the
   watch brief, and the supervisor calling the JIT arrival (RTA − 2 h) "the RTA", in English and in Arabic → two code
   rules (`arrival.sign_problems`, `arrival.rta_label_problems`) in the arrival Validator, the watch brief (sign) and
   the supervisor's check when the arrival tool is cited; the final run's texts are free of both ("consuming 160.2 t
   of fuel instead of 283.2 t"; the Arabic answer names the RTA 2026-09-18T09:30Z).
7. **The supervisor's tool opened arrival threads the check did not track** (two stray threads after Phase 8) → Phase
   8 deletes every arrival thread of its identity at the clock's day; the thread-name test asserts the next free
   number instead of a count.

Regressions after the shared changes (2026-11-15): `Supervisor_check` ✅, `Supervisor_tools_check` ✅ (union 15),
`Stage2_eval` Phases 1–3 ✅ (0 calls), `Stage2_tools_check` ✅, `Tools_check` ✅, `Scheduler_check` 6 / 6,
`Voyage_watch_check` Phases 1–7 + 4s ✅ (D-J7), `Route_advice_check` ✅, lint ratchet 0.
