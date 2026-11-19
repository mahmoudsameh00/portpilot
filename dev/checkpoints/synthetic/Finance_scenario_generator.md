# Finance_scenario_generator — Final Checkpoint

Script: `dev/build/synthetic/Finance_scenario_generator.py` · plan: `docs/plans/Traffic_billing_link_plan.md`
Phase 2 (2026-11-08) · owner decision D-TL-3 ("a stronger planted link, labelled").

## What it does
It re-dates the 2025 invoices so that weekly billing follows the real 2025 Suez traffic, with a planted
amplification α. Amounts, vessels, customers and each payment's delay are kept. Its outputs:
- `db/migrations/026_finance_scenario.sql`: schema `finance_scenario` with `scenario_info`, `invoices`, `payments`
  and twins of eight finance views, built from their live definitions;
- CSV mirrors and a manifest.

## Steps and results
| Phase | Result |
|---|---|
| 1 Inputs (read-only) | 1,000 invoices, 994 payments, 996 invoices in weeks 1–52, 52 transit weeks, 8 view definitions |
| 2 α search (seed 42, 2,000 draws, grid 1.0 … 5.0 step 0.1) | link rate at 52 weeks: α 1.0 → 0.663 … 1.5 → 0.945, **1.6 → 0.972** (chosen; α max 5.12 keeps every weight positive) |
| 3 Re-dating (seed 43) | weekly counts 7 … 31 = the draw; no 2024 date; amounts and vessels unchanged; realized r 0.506 / 0.468 / 0.497 at 13 / 26 / 52 weeks (thresholds 0.555 / 0.392 / 0.277) |
| 4 Payments | 994; each delay kept (20 … 160 days, the sorted lists identical); 176 now fall after 2025-12-28 |
| 5 Migration | 8 twin views with no live `invoices` / `payments` / finance-twin reference left; every comment carries the α label |
| 6 CSVs + manifest | reload: 1,000 / 994 rows, unique invoice numbers; a re-run changes 0 files |
| 7 Views = reference | pending until 026 is applied (billed, count, collected, payments, AR, overdue for 52 weeks vs pandas) |

**Dry run of 026 (rolled back):** 0 errors. Scenario and live both bill 996 invoices and 267,892,000.68 SDR; only the
timing differs. r(invoice count, weekly transits) in SQL is 0.497 for the scenario (= Python) and 0.020 for the
live data.

## Problems and fixes
- Running the script needs `PYTHONPATH` = the project root when it is not run through `dev/tools/run.py`. `run.py`
  itself cannot hash the lock file of the running evaluation (D-TL-2).
- pyright flagged pandas groupby typing and psycopg string queries. Weekly sums are now done in plain Python and the
  queries are parameterised; the outputs are byte-identical.
- **D-TL-4:** a first SQL probe gave r 0.265 because `(date − 2024-12-30) / 7` truncates toward zero and put the lag
  week's days into week 1. The fix is `floor(… / 7.0)`; `verify_readonly.sql` §26 had the same flaw and is fixed.
