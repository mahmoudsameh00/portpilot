# Run lifecycle — Final Checkpoint

This database-free check covers the first execution-reliability slice of the approved
`docs/plans/Project_validation_and_continuation_plan.md` (R1 and the executor portion of R2).

Phase 1 checks that malformed worker output ends with a visible failure, the final-record callback receives
failure, structured pack problems become readable API strings, valid results publish answer/done, and a failed
final-record callback cannot report success. Phase 2 holds a worker with a threading Event, invokes the real
timeout handler, and checks that the worker still consumes capacity and owns its conversation. An expired queued
job never executes. Shutdown cancels waiting jobs visibly, and a late worker cannot replace its timeout result.
Rejected submissions release their thread reservation. Phase 3 starts eight simultaneous submissions against
one worker and one queue slot and verifies exactly two admissions and six busy responses.

The runner counts admitted work until its Future completes, separately from the client-visible state. Timers
cancel queued Futures; running Python threads cannot be forcibly stopped. `Run.check_active()` provides a
cooperative guard; wiring it into graph mutation/publication boundaries is still pending with the approval fixes.
Both normal and request-based pack decisions share one result normalizer; the detailed PackView is unchanged.

The check uses controlled Events and bounded waits, no database, model, or network calls. Run it through
`uv run python tools/run.py pipelines/scripts/agents/Run_lifecycle_check.py`; the runner verifies zero changes to
data and migration artifacts. It is also included in the database-free CI job.
