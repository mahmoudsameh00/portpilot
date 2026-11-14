"""Suez transits loader — IMF PortWatch daily Suez Canal transits for the 2025 report weeks (traffic-billing link plan,
Phase 1, `docs/plans/Traffic_billing_link_plan.md` §3a / §3b / §3b').

Reads:   IMF PortWatch Daily_Chokepoints_Data (public ArcGIS API, portid chokepoint1 = Suez Canal), through the same
         fetch as the agent tool `external.suez_transits`; the first run keeps the raw answer in
         Data/processed/structured/portwatch_suez_raw.json and later runs reuse it (`--refresh` fetches again:
         PortWatch revises past days, so a refresh is a choice, not automatic).
         Data/processed/synthetic/invoices.csv (only the count of 2025 invoices, for the scenario's expected r).
         Data/processed/agents/tool_cache/suez_transits.jsonl (if present: the agent tool's cached days, a cross-check).
Writes:  Data/processed/structured/suez_transits_daily.csv (one row per day, 2024-12-23 … 2025-12-28),
         Data/processed/structured/suez_transits_manifest.json (counts, weekly swing, the scenario's expected r, SHA-256),
         db/migrations/025_suez_transits.sql (schema `external` + table `external.suez_transits_daily`; applied by the
         owner or by the assistant on the owner's word, db/README.md).
Safe to re-run: yes — without `--refresh` the same raw file gives byte-identical outputs (files changed: 0).
Run:     uv run python tools/run.py pipelines/scripts/structured/Suez_transits_loader.py
"""
# %% Phase 0 — Setup
# Why a table and not the agent's JSON cache: the link measure must be one SQL definition next to the KPI views
# (ADR-047), joinable to billing and readable by Power BI (plan decision L2). PortWatch data is public (level 1).
import hashlib
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pandas as pd

# The script's own folder, not the project root, is on sys.path when it is run by path (tools/run.py).
sys.path.insert(0, str(next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists())))
from pipelines.agents.tools import external
from pipelines.lib.common import project_root

ROOT = project_root()
OUT = ROOT / "Data" / "processed" / "structured"
RAW = OUT / "portwatch_suez_raw.json"
CSV = OUT / "suez_transits_daily.csv"
MANIFEST = OUT / "suez_transits_manifest.json"
MIGRATION = ROOT / "db" / "migrations" / "025_suez_transits.sql"
INVOICES = ROOT / "Data" / "processed" / "synthetic" / "invoices.csv"
TOOL_CACHE = ROOT / "Data" / "processed" / "agents" / "tool_cache" / "suez_transits.jsonl"

WEEK1_MONDAY = date(2024, 12, 30)            # ISO 2025-W01 (docs/finance_metrics.md)
FIRST_DAY = WEEK1_MONDAY - timedelta(days=7)  # the week before W01: lag 1 needs it
LAST_DAY = date(2025, 12, 28)                # ISO 2025-W52 Sunday
N_DAYS = (LAST_DAY - FIRST_DAY).days + 1     # 371
COUNT_FIELDS = ("n_total", "n_container", "n_tanker", "n_dry_bulk", "n_general_cargo", "n_roro")
TYPE_FIELDS = COUNT_FIELDS[1:]
SEED, DRAWS = 42, 2000
REFRESH = "--refresh" in sys.argv
print(f"window {FIRST_DAY} … {LAST_DAY} ({N_DAYS} days); refresh={REFRESH}")


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# %% Phase 1 — Fetch PortWatch (or reuse the raw file)
# The service answers at most 1,000 records per query and the tool's window rule is < 120 days, so the year is asked
# in windows of 119 days with the tool's own fetch (same URL, fields and shape checks).
if RAW.exists() and not REFRESH:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    print(f"raw reused: {RAW.name} (retrieved {raw['retrieved_at']})")
else:
    rows, start = [], FIRST_DAY
    with httpx.Client(timeout=30.0) as client:
        while start <= LAST_DAY:
            end = min(start + timedelta(days=external.MAX_WINDOW_DAYS - 1), LAST_DAY)
            rows += external._fetch_transits(external.TransitArgs(start=start, end=end))(client)
            start = end + timedelta(days=1)
    raw = {"source": external.PORTWATCH_URL.removesuffix("/query"), "portid": external.SUEZ_PORTID,
           "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "rows": rows}
    RAW.write_text(json.dumps(raw, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"fetched {len(rows)} rows → {RAW.name}")

# validation 1: one row per day, the whole window, non-negative integers
days = pd.DataFrame(raw["rows"])
days["date"] = pd.to_datetime(days["date"]).dt.date
days = days.sort_values("date").reset_index(drop=True)
assert days["date"].is_unique, "a day appears twice"
assert days["date"].iloc[0] == FIRST_DAY and days["date"].iloc[-1] == LAST_DAY, "the window is not covered"
gaps = sorted(set(FIRST_DAY + timedelta(days=i) for i in range(N_DAYS)) - set(days["date"]))
assert not gaps, f"missing days: {gaps[:5]}"
assert bool((days[list(COUNT_FIELDS) + ["capacity"]].to_numpy() >= 0).all()), "a negative count"
snapshot = {"days": N_DAYS, "first": str(FIRST_DAY), "last": str(LAST_DAY)}
actual = {"days": len(days), "first": str(days["date"].iloc[0]), "last": str(days["date"].iloc[-1])}
assert actual == snapshot, actual
print(f"days {len(days)}; n_total min / mean / max {days.n_total.min()} / {days.n_total.mean():.1f} / "
      f"{days.n_total.max()}")
print("✅ Phase 1 validation passed.")

# %% Phase 2 — Cross-checks: the type split and the agent tool's cached days
# n_total vs the sum of the five types: PortWatch's types need not cover every vessel, so the residual is reported
# (never negative), not assumed zero. The tool cache holds the days the packs already used: the same day must carry
# the same counts, else the loader and the packs would read different data.
resid = days["n_total"] - days[list(TYPE_FIELDS)].sum(axis=1)
resid_days = int(np.count_nonzero(resid.to_numpy()))
print(f"n_total − Σ types: min {resid.min()}, max {resid.max()}, days with a residual {resid_days}")
assert resid.min() >= 0, "the types add up to more than n_total"

cached, mismatched = {}, []
if TOOL_CACHE.exists():
    for line in TOOL_CACHE.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        for r in e.get("payload") or []:
            cached[date.fromisoformat(r["date"])] = r
by_day = days.set_index("date")
overlap = [d for d in cached if FIRST_DAY <= d <= LAST_DAY]
for d in overlap:
    if any(int(by_day.at[d, f]) != int(cached[d][f]) for f in COUNT_FIELDS):
        mismatched.append(str(d))
print(f"tool-cache days in the window: {len(overlap)}; different counts: {len(mismatched)} {mismatched[:5]}")
assert not mismatched, "PortWatch revised days the packs already used: decide before loading (plan §6)"
print("✅ Phase 2 validation passed.")

# %% Phase 3 — Weekly transits and their swing
# Week 0 = 2024-12-23 … 29 (lag 1 for week 1); weeks 1–52 = the report weeks of docs/finance_metrics.md.
days["week"] = days["date"].map(lambda d: (d - WEEK1_MONDAY).days // 7 + 1)
weekly = days.groupby("week").agg(transits=("n_total", "sum"), n_days=("n_total", "count"))
assert list(weekly.index) == list(range(0, 53)) and (weekly["n_days"] == 7).all(), "a week is not 7 days"
w = weekly.loc[1:52, "transits"].astype(float)
swing = {"weekly_mean": round(float(w.mean()), 1), "weekly_sd": round(float(w.std(ddof=1)), 1),
         "weekly_cv_pct": round(float(w.std(ddof=1) / w.mean() * 100), 2),
         "weekly_min": int(w.min()), "weekly_min_week": int(w.idxmin()),
         "weekly_max": int(w.max()), "weekly_max_week": int(w.idxmax()),
         "lag1_autocorr": round(float(np.corrcoef(w.values[:-1], w.values[1:])[0, 1]), 3)}
print("weekly swing:", swing)
print("✅ Phase 3 validation passed.")

# %% Phase 4 — The scenario's expected r, written before the scenario exists (plan §3b' / §4)
# Scenario model (Phase 2 of the plan): the 2025 invoices of weeks 1–52 spread over the weeks by a multinomial draw
# with weights = weekly transits. The measure is Pearson r (invoice count vs transits, lag 0) over weeks 1…n, and a
# "link" when |r| ≥ 2 / √n. Simulated here with a fixed seed: the median r, its 5th percentile, and how often the rule
# says "link" at n = 13 and n = 52. The live data (uniform dates) is the null: E[r] ≈ 0, and the rule's false rate at
# lag 0 alone ≈ 5 %.
inv = pd.read_csv(INVOICES, usecols=["invoice_date"])
inv_d = pd.to_datetime(inv["invoice_date"]).dt.date
n_inv = int(((inv_d >= WEEK1_MONDAY) & (inv_d <= LAST_DAY)).sum())
p = (w / w.sum()).values
rng = np.random.default_rng(SEED)
counts = rng.multinomial(n_inv, p, size=DRAWS)
uniform = rng.multinomial(n_inv, np.full(52, 1 / 52), size=DRAWS)


def r_of(c, n):
    x, y = c[:n].astype(float), w.values[:n]
    return float(np.corrcoef(x, y)[0, 1])


expect: dict[str, Any] = {"invoices_weeks_1_52": n_inv, "draws": DRAWS, "seed": SEED}
for n in (13, 26, 52):
    rs = np.array([r_of(c, n) for c in counts])
    r0 = np.array([r_of(c, n) for c in uniform])
    thr = 2 / np.sqrt(n)
    expect[f"n{n}"] = {"threshold": round(float(thr), 3), "scenario_r_median": round(float(np.median(rs)), 3),
                       "scenario_r_p05": round(float(np.percentile(rs, 5)), 3),
                       "scenario_link_rate": round(float((np.abs(rs) >= thr).mean()), 3),
                       "uniform_r_median": round(float(np.median(r0)), 3),
                       "uniform_link_rate": round(float((np.abs(r0) >= thr).mean()), 3)}
    print(f"n={n}: threshold {thr:.3f} | scenario r median {expect[f'n{n}']['scenario_r_median']} "
          f"(p05 {expect[f'n{n}']['scenario_r_p05']}), link rate {expect[f'n{n}']['scenario_link_rate']} | "
          f"uniform r median {expect[f'n{n}']['uniform_r_median']}, link rate {expect[f'n{n}']['uniform_link_rate']}")
assert abs(expect["n52"]["uniform_r_median"]) < 0.05, "the null should centre on 0"
print("✅ Phase 4 validation passed.")

# %% Phase 5 — Write the CSV, the migration and the manifest; reload and re-validate
out = days[["date", *COUNT_FIELDS, "capacity"]].copy()
out["date"] = [d.isoformat() for d in out["date"]]
out.to_csv(CSV, index=False, lineterminator="\n")

retrieved = raw["retrieved_at"]
values = ",\n".join(
    f"('{r['date']}', {r['n_total']}, {r['n_container']}, {r['n_tanker']}, {r['n_dry_bulk']}, "
    f"{r['n_general_cargo']}, {r['n_roro']}, {r['capacity']}, '{retrieved}')" for r in (dict(zip(out.columns, row)) for row in out.itertuples(index=False, name=None)))
cols = {
    "date": "Day (UTC) of the PortWatch estimate",
    "n_total": "Transit calls through the Suez Canal that day, all vessel types (PortWatch n_total)",
    "n_container": "Container ship transits that day",
    "n_tanker": "Tanker transits that day",
    "n_dry_bulk": "Dry bulk carrier transits that day",
    "n_general_cargo": "General cargo ship transits that day",
    "n_roro": "Ro-ro ship transits that day",
    "capacity": "Summed capacity of the transits that day, as PortWatch reports it (its own unit)",
    "retrieved_at": "When the loader fetched this row from PortWatch (UTC); PortWatch revises past days"}
sql = f"""-- 025_suez_transits.sql — generated by pipelines/scripts/structured/Suez_transits_loader.py (do not edit by hand)
-- Traffic-billing link plan Phase 1 (docs/plans/Traffic_billing_link_plan.md §3a): IMF PortWatch daily Suez Canal
-- transits {FIRST_DAY} … {LAST_DAY} ({N_DAYS} days; the week before ISO 2025-W01 is kept for lag 1).
-- Public data, sensitivity level 1. Source: {raw['source']} (portid {raw['portid']}), retrieved {retrieved}.
BEGIN;

CREATE SCHEMA external;
COMMENT ON SCHEMA external IS 'Public external data loaded into the database (level 1), read by the finance views that relate PortPilot to the outside world (traffic-billing link plan)';

CREATE TABLE external.suez_transits_daily (
    date            date PRIMARY KEY,
    n_total         integer NOT NULL CHECK (n_total >= 0),
    n_container     integer NOT NULL CHECK (n_container >= 0),
    n_tanker        integer NOT NULL CHECK (n_tanker >= 0),
    n_dry_bulk      integer NOT NULL CHECK (n_dry_bulk >= 0),
    n_general_cargo integer NOT NULL CHECK (n_general_cargo >= 0),
    n_roro          integer NOT NULL CHECK (n_roro >= 0),
    capacity        bigint  NOT NULL CHECK (capacity >= 0),
    retrieved_at    timestamptz NOT NULL,
    CHECK (n_total >= n_container + n_tanker + n_dry_bulk + n_general_cargo + n_roro)
);
COMMENT ON TABLE external.suez_transits_daily IS 'IMF PortWatch daily Suez Canal transits (AIS-based estimates, public, level 1), {FIRST_DAY} … {LAST_DAY}; loaded by Suez_transits_loader.py; read by finance.kpi_traffic_link (migration 026+)';
""" + "".join(f"COMMENT ON COLUMN external.suez_transits_daily.{c} IS '{t.replace(chr(39), chr(39) * 2)}';\n"
            for c, t in cols.items()) + f"""
INSERT INTO external.suez_transits_daily (date, n_total, n_container, n_tanker, n_dry_bulk, n_general_cargo, n_roro,
                                          capacity, retrieved_at) VALUES
{values};

GRANT USAGE ON SCHEMA external TO ports_readonly;
GRANT SELECT ON external.suez_transits_daily TO ports_readonly;

COMMIT;
"""
MIGRATION.write_text(sql, encoding="utf-8", newline="\n")

back = pd.read_csv(CSV)
assert len(back) == N_DAYS and list(back.columns) == ["date", *COUNT_FIELDS, "capacity"], "CSV reload"
assert back["n_total"].tolist() == days["n_total"].tolist(), "CSV values differ"
assert MIGRATION.read_text(encoding="utf-8").count("\n('") == N_DAYS, "migration row count"   # every row starts a line

manifest = {"plan": "docs/plans/Traffic_billing_link_plan.md (Phase 1)", "source": raw["source"],
            "portid": raw["portid"], "retrieved_at": retrieved, "window": [str(FIRST_DAY), str(LAST_DAY)],
            "days": N_DAYS, "weeks": "0 (lag) + 1–52", "n_total_type_residual_days": resid_days,
            "tool_cache_days_checked": len(overlap), "weekly_swing": swing, "scenario_expected_r": expect,
            "files": {p.relative_to(ROOT).as_posix(): sha256(p) for p in (RAW, CSV, MIGRATION)}}
MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(f"wrote {CSV.name} ({len(back)} rows), {MIGRATION.name}, {MANIFEST.name}")
print("✅ Phase 5 validation passed.")

# %% Final Checkpoint
# Narrative: pipelines/checkpoints/structured/Suez_transits_loader.md
final = {"days": len(days), "weeks": int(len(weekly)), "type_residual_never_negative": bool(resid.min() >= 0),
         "tool_cache_mismatches": len(mismatched), "migration": MIGRATION.name}
assert final == {"days": N_DAYS, "weeks": 53, "type_residual_never_negative": True, "tool_cache_mismatches": 0,
                 "migration": "025_suez_transits.sql"}, final
print("✅ Final Checkpoint passed.")
