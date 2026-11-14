# Suez_transits_loader — Final Checkpoint

Script: `pipelines/scripts/structured/Suez_transits_loader.py` · plan: `docs/plans/Traffic_billing_link_plan.md`
Phase 1 (2026-11-08).

## What it does
It fetches IMF PortWatch daily Suez Canal transits for 2024-12-23 … 2025-12-28, one row per day (371 days). The
first week is the one before ISO 2025-W01, kept so that lag 1 has data. It writes:
- the raw answer (reused on later runs; `--refresh` fetches again);
- a CSV that mirrors the future table;
- `db/migrations/025_suez_transits.sql` (schema `external`, table `external.suez_transits_daily`, level 1);
- a manifest that records the weekly swing and the scenario's expected r.

## Steps and results
| Phase | Result |
|---|---|
| 1 Fetch | 371 rows in 4 windows of ≤ 119 days (the tool's own fetch and shape checks); no gap, no duplicate, no negative; `n_total` 18 … 61 per day, mean 38.4 |
| 2 Cross-checks | `n_total` = the sum of the five types on every day (residual 0); all 371 days are also in the agent tool's cache, and every count is identical (0 mismatches: the packs and this table read the same data) |
| 3 Weekly swing | weeks 1–52: mean 269.6 transits, sd 21.5 (**CV 7.99 %**), min 217 (week 6), max 315 (week 37), lag-1 autocorrelation 0.439 |
| 4 Expected r (seed 42, 2,000 draws, 996 invoices in weeks 1–52) | see below |
| 5 Write + reload | the CSV reloads equal; the migration holds 371 rows; the manifest has SHA-256 hashes; a re-run changes 0 files |

**Expected r, written before the scenario exists** (scenario = invoices spread over the weeks in proportion to the
weekly transits; "link" when |r| ≥ 2 / √n):

| n weeks | threshold | scenario r median (p05) | scenario "link" rate | uniform (live-like) r median | uniform "link" rate |
|---|---|---|---|---|---|
| 13 | 0.555 | 0.288 (−0.197) | 11.3 % | −0.003 | 5.1 % |
| 26 | 0.392 | 0.234 (−0.097) | 18.9 % | −0.006 | 5.9 % |
| 52 | 0.277 | 0.332 (0.124) | 66.3 % | 0.002 | 4.3 % |

**Reading:** the real 2025 traffic moves only about 8 % from week to week, while about 19 invoices a week give a
count noise of about 23 %. So even a scenario where billing truly follows traffic is detected only about 2 times in
3 over the full year, and rarely within 13 weeks. This finding goes back to the owner (plan §3b') before the
scenario generator is written.

## Problems and fixes
- `tools/run.py` could not hash `Data/processed/agents/eval/llm_cache/openrouter/locks/c99.lock`: a lock held by
  another process (the external-context plan's evaluation was running). The file was not touched. The script was run
  directly (`PYTHONPATH` = the project root, log in `Notebooks/_scratch/`), and the "files changed" check was done
  with SHA-256 before and after (0 on a re-run).
- The migration row-count assert expected N − 1 rows (each row starts a line, so it is N). Fixed.
- A column comment held an apostrophe ("day's"), which would have broken the SQL string. The wording was changed and
  every comment is now quote-escaped.
- pyright flagged pandas-typing patterns (`.all().all()`, `itertuples` attributes, `to_dict` overloads). These were
  rewritten with numpy / plain tuples; the outputs are byte-identical; ruff and pyright are clean.
