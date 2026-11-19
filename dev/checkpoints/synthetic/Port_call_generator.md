# Final Checkpoint — Port_call_generator (JIT arrival plan D-J1, 2026-11-15)

**What it makes:** 680 synthetic port-call messages (the Requested Time of Arrival a port or agent sends a vessel) for
the 500 port calls of the synthetic voyages — `Data/processed/synthetic/port_calls/port_call_messages.csv`, its
`manifest.json` (the scenario per call: ground truth for checks, never a column) and `db/migrations/030_port_call_messages.sql`
(the table + the same rows; applied 2026-11-15). Seed `numpy default_rng([42, 30])`; a re-run writes nothing new.

| Phase | Step | Result |
|---|---|---|
| 1 | Inputs: the voyage file; the port's view = the declared schedule (departure + route / service speed) | 500 voyages, scheduled arrivals 2026-09-03 … 2026-11-23; `arrival_ts` (the ETA answer key, P9-7) never read |
| 2 | The berth plan: a scenario per call → the RTA, the first message 72–120 h before the scheduled arrival (never before departure + 1 h), revisions (30 %, 12–36 h later, −12…+24 h) and cancellations | on time 129, berth later 184, much later 60, earlier 102, cancelled 25; 155 calls revised; every message sent before its requested time |
| 3 | Save + migration 030 | CSV + manifest + migration written; reload equal |

## Problems and fixes
1. **A first message rounded to the minute fell a few seconds before departure + 1 h** (the Phase 2 assertion) → the
   send time is rounded **up** to the minute (`ceil`).

## Why the shape
A real RTA arrives as a port-call message (IMO *Just In Time Arrival Guide*; IHO S-211 / DCSA JIT timestamps): sender,
send time, port call, location, revisions and cancellations. The tools read "the latest message sent at or before the
clock" — the same rule for these rows and for real ones (`real_or_synthetic = 'real'`), so real data needs no code change.
