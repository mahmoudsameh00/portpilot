---
name: arrival-advice
description: How to advise the speed for a Just-in-Time arrival from the arrival_advice evidence: the rule (the cheapest option at the berth by the RTA), when a cited risk may overrule it, numbers as slots, dates copied.
stage: 2
reviewed_by_owner: no
---
# Arrival advice (Just-in-Time arrival)

The port asked this vessel to arrive at a time (the RTA, Requested Time of Arrival). Keep the speed and wait at
anchor, or slow down and arrive just in time? Code computed every number; you choose and explain. Never recompute,
estimate or round a number.

## The evidence
- `arrival.summary` (one row): `rta_utc`, `rta_source` (the port's message or the question), `location`, `margin_h`,
  `target_utc` (RTA − margin), `situation` (early / on_time / late), `current_speed_kn`, `service_speed_kn`,
  `floor_speed_kn` (the lowest speed allowed), `keep_arrival_utc`, `keep_wait_h`, `keep_late_h`, `suez_ahead`,
  `rule_option` (the rule's choice) and its `rule_change_fuel_t` / `rule_change_fuel_sdr` against keeping the speed.
- `arrival.options`, rows keyed by `option`: `keep` (current speed, then wait), `jit` (reaches the target exactly),
  `floor` (lowest allowed speed, then wait the rest), `catch_up` (faster, up to the service speed), `cape` (round the
  Cape at the speed that fits, only when the delay cannot be absorbed via Suez). Fields: `speed_kn`, `distance_nm`,
  `sea_h`, `arrival_utc`, `wait_h`, `late_h`, `arrives_by_rta`, `fuel_t`, `fuel_sdr`, `suez_dues_sdr`, `total_sdr`,
  and against `keep`: `change_fuel_t`, `change_fuel_sdr`, `change_total_sdr`.
- `arrival.weather`: a `weather` row (keyed by `kind`) when the next legs meet the storm rule; `arrival.traffic`
  (canal ahead): `change_transits_pct`. Either may say "context unavailable".

## The decision rule
1. Recommend `rule_option`: the cheapest option at the berth by the RTA; when none is, the least late.
2. Another option **only** when a cited risk justifies it, as your first reason: a `weather` row in `arrival.weather`
   (e.g. keep speed to pass ahead of a storm), or `change_transits_pct` of −20 % or lower in `arrival.traffic`.
3. No risk evidence means rule 1. Never invent a risk. Waiting is priced by its fuel only, never by time.

## Writing ArrivalAdvice
- `recommendation`: an option of `arrival.options`. `headline`: one sentence, the speed to sail and why.
- `reasons`: 1 to 5 sentences: arrival against the RTA, fuel and money, waiting hours, risk. Each lists its
  `evidence_ids`. `risks`: weather and traffic only, or "context unavailable" when a tool said so.
- **Every number is a slot**: `{arrival.options[jit]:speed_kn}`, `{arrival.summary:keep_wait_h}`. Formats: money
  `sdr` / `k` / `M`, speed `kn`, tonnes `t` / `t0`, distance `nm`, hours `h`. A slot writes its own unit and sign:
  no "kn", "t", "h", "SDR" or "+" beside it. A change field carries its sign ("−160.5 t"): prefer the two options'
  own values ("{arrival.options[jit]:fuel_t} instead of {arrival.options[keep]:fuel_t}").
- Literal numbers: dates and times copied exactly from the evidence only (`rta_utc`, `target_utc`, an option's
  `arrival_utc`, e.g. 2026-09-15T14:00Z). The port by its UN/LOCODE.
- Code writes the option table, the assumptions and the sources: do not repeat them.

## Examples
- Early: "Slow to {arrival.options[jit]:speed_kn} instead of waiting {arrival.summary:keep_wait_h} at anchor:
  {arrival.options[jit]:fuel_t} of fuel instead of {arrival.options[keep]:fuel_t}."
- Very early: "Sail at the lowest allowed speed, {arrival.options[floor]:speed_kn}; the vessel still waits
  {arrival.options[floor]:wait_h}."
- Late: "Keep the speed: the vessel reaches the berth {arrival.options[keep]:late_h} after the requested time and no
  faster speed is available."
