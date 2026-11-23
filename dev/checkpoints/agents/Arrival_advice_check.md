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

**2026-11-22 — the owner's review of the skill (Azure staging plan D-AZ-4; ADR-070 note 2026-11-22).** The skill's
text was edited (the RTA's location, the tie order, "RTA" = `rta_utc` only, the risk directions; body 1,198 of 1,200
tokens: the first draft was 1,284 and Phase 4s refused it) and the Validator gained the risk's direction. Phase 4
gained six direction cases (cases 13, 19 and 1): the Suez drop justifies the Cape only, a storm an earlier arrival
than the rule's and never the Cape. Phase 8 can now run a second time on its own reply cache (`EVAL_REPEAT=2`,
ADR-052): run 1 7 / 8 (Gemini 503 → the fallback model; case 4 `output_invalid`), run 2 8 / 8; one patch per
advice in both, mostly a date written as a slot (an old habit: 25 of 53 replies under the old text).

The owner's fresh retry (`EVAL_REPEAT=3`) scored **6 / 8** in Phase 8 with 23 calls, zero cache hits and seven
patches. Case 1 supplied `arrival.options[jit]` as an evidence ID and case 7 cited `arrival.traffic`, which was
absent from its evidence. Both yielded no recommendation. The six accepted cases matched the rule, the supervisor
answered in English and Arabic, and the watch brief passed. The eight-case assertion failed. The owner had chosen
to accept the earlier results for staging if this retry fell short (Azure staging plan §7).

**2026-11-23 — rounded JIT speed.** The web replay for vessel 38 exposed a two-minute difference between its
ETA and the planning target. Phase 4 now exercises an ETA two minutes after, one minute before and exactly on
the target, including English and Arabic target claims and a valid comparison with the port deadline. Phase 4s
reads the revised 1,182-token skill and renders its 11 example slots. Each evaluation's arrival threads use a
unique prefix so cleanup can run alongside a signed-in user and preserve their saved advice.
The first browser retry withheld the recommendation because the writer put the ETA and RTA in numeric placeholders.
Phase 4 now also checks exact UTC copying for a cited option and summary, plus rejection of an uncited source,
an unknown row and an unknown field.
The second browser result compared the JIT ETA correctly but called 55.1 hours of planned waiting the time
before the deadline. The margin was two hours. Phase 4 checks that wording in English and Arabic and accepts
the duration as planned waiting at anchor.

**Watch decisions, 2026-11-23.** Phases 1–7 passed. The arithmetic checks cover full-precision late arrivals,
including a missed deadline whose rounded delay is 0.0 hours. Phase 6w checks all 41 timing results, restored
older snapshots, the no-RTA and stationary cases, and the calculated fallback. The signed-in replay displayed
219 ETA rows and 41 results. Vessels 2, 351, 352 and 157 can recover 1, 4, 3 and 7 minutes respectively.
Twelve late vessels had no faster option. The operational brief remained readable without exposing its receipts.

Repeat 9 accepted six of eight real recommendations, all matching the computed choice, with 17 provider calls,
zero cache hits and eight patches. Case 2 phrased a signed fuel change as a saving. Case 7 omitted its option
evidence IDs. The validator withheld both. The Arabic supervisor answered and the watch brief passed. The English
supervisor response failed validation. The eight-case gate remains 8/8.
