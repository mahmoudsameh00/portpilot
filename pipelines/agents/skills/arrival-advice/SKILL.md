---
name: arrival-advice
description: How to advise the speed for a Just-in-Time arrival from the arrival_advice evidence: the rule (the cheapest option at the RTA's location by the RTA), when a cited risk may overrule it and in which direction, numbers as slots, dates copied.
stage: 2
reviewed_by_owner: 2026-11-22
---
# Arrival advice (Just-in-Time arrival)

Explain the computed sailing options for the port's Requested Time of Arrival (RTA). Copy the figures from evidence.

## The evidence
- `arrival.summary` (one row): `rta_utc`, `rta_source` (the port's message or the question), `location`, `margin_h`,
  `target_utc` (RTA − margin), `situation` (early / on_time / late), `current_speed_kn`, `service_speed_kn`,
  `floor_speed_kn` (lowest allowed), `keep_arrival_utc`, `keep_wait_h`, `keep_late_h`, `suez_ahead`, `rule_option`
  and its `rule_change_fuel_t` / `rule_change_fuel_sdr` against keeping the speed.
- `arrival.options`, rows keyed by `option`: `keep` (current speed, then wait), `jit` (aims for the target),
  `floor` (lowest allowed speed, then wait), `catch_up` (faster, up to the service speed), `cape` (round the Cape,
  only when the floor via Suez still waits). Fields: `speed_kn`, `distance_nm`,
  `sea_h`, `arrival_utc`, `wait_h`, `late_h`, `arrives_by_rta`, `fuel_t`, `fuel_sdr`, `suez_dues_sdr`, `total_sdr`,
  and against `keep`: `change_fuel_t`, `change_fuel_sdr`, `change_total_sdr`.
  Quote `wait_h` as planned waiting at anchor until the planning target. The margin separates that target from the RTA.
- `arrival.weather`: a `weather` row when the next legs meet the storm rule; `arrival.traffic` (canal ahead):
  `change_transits_pct`. Either may say "context unavailable".

## The decision rule
1. Recommend `rule_option`: the cheapest allowed-speed option at the RTA's `location` (berth or pilot boarding place)
   by the RTA; when none is, the least late, then the cheapest.
2. Another option **only** when your first reason cites a risk in its direction:
   - a `weather` row in `arrival.weather` → an option arriving earlier than the rule's (pass ahead of the storm),
     never `cape`;
   - `change_transits_pct` ≤ −20 % in `arrival.traffic` (ships avoiding the canal) → `cape` only.
3. No risk evidence means rule 1. Never invent a risk. Waiting is priced by its fuel only, never by time.

## Writing ArrivalAdvice
- `recommendation`: an option of `arrival.options`. `headline`: one sentence, the speed to sail and why.
- `reasons`: 1 to 5 sentences (arrival vs the RTA, fuel and money, waiting, risk), each with its `evidence_ids`.
  `risks`: weather and traffic only, or "context unavailable" when a tool said so.
- **Every number is a slot**: `{arrival.options[jit]:speed_kn}`, `{arrival.summary:keep_wait_h}`. Formats: money
  `sdr` / `k` / `M`, speed `kn`, tonnes `t` / `t0`, distance `nm`, hours `h`. A slot writes its own unit and sign:
  no "kn", "t", "h", "SDR" or "+" beside it. A change field carries its sign ("−160.5 t"): prefer the two options'
  own values ("{arrival.options[jit]:fuel_t} instead of {arrival.options[keep]:fuel_t}").
- Copy timestamps exactly. Compare an option's ETA (`arrival_utc`) with the port's deadline (`rta_utc`).
  Code compares the rounded JIT speed's ETA with the planning target. Name ports by UN/LOCODE.
- Code writes the option table, assumptions and sources: do not repeat them.

## Examples
- Early: "Slow to {arrival.options[jit]:speed_kn} instead of waiting {arrival.summary:keep_wait_h} at anchor:
  {arrival.options[jit]:fuel_t} of fuel instead of {arrival.options[keep]:fuel_t}."
- Very early: "Sail at the lowest allowed speed, {arrival.options[floor]:speed_kn}; the vessel still waits
  {arrival.options[floor]:wait_h}."
- Late: "Keep the speed: the vessel reaches the berth {arrival.options[keep]:late_h} after the requested time and no
  faster speed is available."
