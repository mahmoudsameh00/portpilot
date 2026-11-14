# Approval safety — Final Checkpoint

Approved scope: stabilization plan Phase 1, R2–R4. This check reads application code and writes no data.
All connections and graph work are stubbed; it does not claim live PostgreSQL contention was tested.

1. The CLI and API contend on the same advisory-lock key, using the checkpoint login. A second thread remains
   independent, and exceptions release the lock. The API translates a busy lock to a 409 problem.
2. Nine review inputs invalidate the version: draft, charts, analysis, evidence, approval history, revision,
   status, validation verdict, and readiness. Direct decisions require the version. A simulated chart edit
   between HTTP acceptance and worker execution prevents graph resume; a pack that stopped waiting also refuses.
3. Expired runs cannot enter approval/publication or start another graph node/tool through the API callbacks.
   The API context carries a callable guard outside persisted/model-visible state. Already-running provider or
   database calls cannot be forcibly cancelled; checks are cooperative at operation boundaries.
4. A scheduler re-plans under the thread lock before streaming. Retention rechecks the latest checkpoint under
   the same lock before archival/deletion, preserving refreshed or active threads.

Both direct and request-confirm API paths recheck the review under the lock. A stale request detected before
admission returns HTTP 409; if detected after admission, its run ends with a failed event containing status 409.
`PackView.draft_sha` supplies the version to the browser. The command-line `show` prints it; direct
`Weekly_pack.py resume --decision ... --draft-sha <version>` requires it. Existing proposals must be read again
after deploying the widened version hash. No database migration is required.

API, CLI, scheduler, nested supervisor route advice and retention use `pipelines/agents/locks.py`. New-thread
entry points also check that the selected checkpoint ID is still unused after taking the lock.

Run with `uv run python tools/run.py pipelines/scripts/agents/Approval_safety_check.py`.
Phases 1–4 pass; the wrapper reports zero data/migration changes. Included in database-free CI.
The owner-run API/Scheduler integration suites still need the loaded databases; `Api_check.py` now sends versions.
