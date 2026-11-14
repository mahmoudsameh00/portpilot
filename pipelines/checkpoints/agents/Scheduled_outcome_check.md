# Scheduled business outcomes — Final Checkpoint

Stabilization R8: a graph returning normally no longer implies a successful scheduled product. A validated pack
waiting for approval, a published pack, a completed watch or an idle schedule exits 0. Stopped/incomplete outcomes
exit 4 and emit a warning. A usable watch with an invalid/missing brief or a published deck awaiting DB sync exits
5, marking degradation while keeping its saved output. Existing exceptions, database-probe failures and invalid
identities retain exits 1/2/3.

The CLI stores the operational classification in its JSONL log. Weekly-pack cron check-ins consume the same exit
code. Voyage watch keeps the existing one-monitor limit: warnings/errors, no second cron monitor.

Validation has two phases: 18 pure policy cases and 24 actual CLI entry-point cases with fake graph execution,
identities and a recording cron transport. Validated pending packs, invalid output, validator failure, missing
data, insufficient access, incomplete results, quiet watches, invalid briefs, quota exceptions, DB failure and
invalid configuration are distinct. Tests verify exit/log/check-in agreement, warning emission and lock cleanup.
No database/provider/Sentry calls; temporary logs are removed. Windows may retry nonzero results under its
existing task policy; this change does not alter replay selection or enable a new scheduler task.
