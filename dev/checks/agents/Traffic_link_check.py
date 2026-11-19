"""Traffic link check — M17 `kpi_traffic_link` (migration 027) against an independent reference, and the rule's power
on planted series (traffic-billing link plan Phase 3, `docs/plans/Traffic_billing_link_plan.md` §3f parts 1–2; part 3,
the Validator's planted sentences, is added in Phase 5).

Reads:   PostgreSQL read-only (PG_RO_USER): the three views finance / finance_test / finance_scenario.kpi_traffic_link;
         for the reference, the base dates only (public.invoices, finance_scenario.invoices, finance_test.invoices).
         Data/processed/structured/suez_transits_daily.csv (the loader's file = external.suez_transits_daily).
Writes:  nothing.
Re-run:  safe (read-only; the planted series use fixed seeds).
Run:     uv run python dev/tools/run.py dev/checks/agents/Traffic_link_check.py  (after 027; ports-postgres up)
"""
# %% Phase 0 — Setup
import datetime as dt
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
from psycopg import sql

# The script's own folder, not the project root, is on sys.path when it is run by path (dev/tools/run.py).
sys.path.insert(0, str(next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists())))
from pipelines.lib.common import load_env, project_root

ROOT = project_root()
load_env(ROOT)
TRANSITS = ROOT / "Data" / "processed" / "structured" / "suez_transits_daily.csv"
WEEK1_MONDAY, WEEK52_SUNDAY = dt.date(2024, 12, 30), dt.date(2025, 12, 28)
TEST_WEEKS = (10, 23, 36, 49)                   # the evaluation copy's weeks (migration 012 / 017)
MIN_WEEKS = 13
DATASETS = ("finance", "finance_test", "finance_scenario")


def pg():
    e = os.environ
    return psycopg.connect(host=e["PGHOST"], port=e["PGPORT"], dbname=e["PGDATABASE"], user=e["PG_RO_USER"],
                           password=e["PG_RO_PASSWORD"], options="-c default_transaction_read_only=on",
                           connect_timeout=5)


def week_of(d: dt.date) -> int:
    return (d - WEEK1_MONDAY).days // 7 + 1          # Python's // is floor: the lag week is week 0


def link_rule(counts: np.ndarray, t0: np.ndarray, t1: np.ndarray) -> list[dict]:
    """M17 for weeks 1…52 from the full series: YTD r at lag 0 / 1, threshold 2 / √n, link and its lag."""
    out = []
    for n in range(1, len(counts) + 1):
        if n < MIN_WEEKS:
            out.append({"r0": None, "r1": None, "thr": None, "link": None, "lag": None})
            continue
        r0 = float(np.corrcoef(counts[:n], t0[:n])[0, 1])
        r1 = float(np.corrcoef(counts[:n], t1[:n])[0, 1])
        thr = 2 / np.sqrt(n)
        p0, p1 = abs(r0) >= thr, abs(r1) >= thr
        lag = 0 if p0 and abs(r0) >= abs(r1) else 1 if p1 else 0 if p0 else None
        out.append({"r0": r0, "r1": r1, "thr": thr, "link": "link" if p0 or p1 else "no_link", "lag": lag})
    return out


# %% Phase 1 — Inputs
with pg() as conn:
    views = {s: pd.DataFrame(conn.execute(sql.SQL(
        "SELECT report_week, invoices_billed, r_lag0, r_lag1, r_threshold, link, link_lag "
        "FROM {}.kpi_traffic_link ORDER BY report_week").format(sql.Identifier(s))).fetchall(),
        columns=["w", "n", "r0", "r1", "thr", "link", "lag"]) for s in DATASETS}
    dates = {s: [r[0] for r in conn.execute(sql.SQL("SELECT invoice_date FROM {}.invoices").format(sql.Identifier(sc)))]
             for s, sc in (("live", "public"), ("scenario", "finance_scenario"), ("test", "finance_test"))}
tr = pd.read_csv(TRANSITS)
weekly: dict[int, int] = {}
for d_, n_ in zip(tr["date"], tr["n_total"]):
    wk = week_of(dt.date.fromisoformat(str(d_)))
    weekly[wk] = weekly.get(wk, 0) + int(n_)
T0 = np.array([weekly[w] for w in range(1, 53)], dtype=float)
T1 = np.array([weekly[w - 1] for w in range(1, 53)], dtype=float)
assert sorted(weekly) == list(range(0, 53)), "transit weeks 0–52"
assert all(len(v) == 52 for v in views.values()), {s: len(v) for s, v in views.items()}
print(f"views: 3 × 52 rows; invoices live {len(dates['live'])}, scenario {len(dates['scenario'])}, "
      f"test copy {len(dates['test'])}")
print("✅ Phase 1 validation passed.")

# %% Phase 2 — The views = an independent reference (all 52 weeks × 3 datasets)
# Counts from the base dates (never from kpi_weekly), transits from the loader's CSV (never from the table), the rule
# in numpy. The test copy = the live weeks with the 4 test weeks counted from finance_test.invoices.


def counts_of(ds: list) -> np.ndarray:
    c = np.zeros(53, dtype=float)
    for d in ds:
        if d <= WEEK52_SUNDAY:
            c[week_of(d)] += 1
    return c[1:]


live = counts_of(dates["live"])
test = live.copy()
tc = counts_of(dates["test"])
for w in TEST_WEEKS:
    test[w - 1] = tc[w - 1]
ref_counts = {"finance": live, "finance_test": test, "finance_scenario": counts_of(dates["scenario"])}
mismatch = []
for s in DATASETS:
    v = views[s]
    assert v["n"].astype(float).tolist() == ref_counts[s].tolist(), f"{s}: weekly counts"
    rows = zip(v["w"], v["r0"], v["r1"], v["thr"], v["link"], v["lag"], link_rule(ref_counts[s], T0, T1))
    for w_, r0_, r1_, thr_, link_, lag_, ref in rows:
        for col, got in (("r0", r0_), ("r1", r1_), ("thr", thr_)):
            want = ref[col]
            if (got is None) != (want is None) or (want is not None and abs(float(got) - round(want, 3)) > 0.0011):
                mismatch.append((s, w_, col, got, want))
        lag = None if lag_ is None or pd.isna(lag_) else int(lag_)
        link_ = None if link_ is None or (isinstance(link_, float) and pd.isna(link_)) else link_  # pandas: NULL → NaN
        if link_ != ref["link"] or lag != ref["lag"]:
            mismatch.append((s, w_, "link", link_, ref["link"], lag, ref["lag"]))
print(f"compared 3 × 52 weeks × (r_lag0, r_lag1, threshold, link, link_lag); mismatches: {len(mismatch)} {mismatch[:3]}")
assert not mismatch
print("✅ Phase 2 validation passed.")

# %% Phase 3 — The answers written before measuring (plan §4) and a reviewed snapshot
link_weeks = {s: [int(w) for w, lk in zip(views[s]["w"], views[s]["link"]) if lk == "link"] for s in DATASETS}
actual = {"live_link_weeks": len(link_weeks["finance"]), "test_link_weeks": len(link_weeks["finance_test"]),
          "scenario_link_weeks": len(link_weeks["finance_scenario"]),
          "scenario_first_link_week": min(link_weeks["finance_scenario"], default=None),
          "scenario_link_at_52": "link" == views["finance_scenario"]["link"].iloc[-1],
          "live_r0_52": float(views["finance"]["r0"].iloc[-1]),
          "scenario_r0_52": float(views["finance_scenario"]["r0"].iloc[-1])}
print("snapshot:", actual)
reviewed = {"live_link_weeks": 0, "test_link_weeks": 0, "scenario_link_weeks": 29, "scenario_first_link_week": 24,
            "scenario_link_at_52": True, "live_r0_52": 0.02, "scenario_r0_52": 0.497}
assert actual == reviewed, actual
print("✅ Phase 3 validation passed.")

# %% Phase 4 — The rule's power on planted series (pure code, seeded)
# 200 series correlated with the real weekly transits at lag 0 (target r ≈ 0.6), 200 at lag 1, 200 independent.
# Done-when (plan §1): ≥ 95 % of planted links flagged at 52 weeks; the false rate on independent series reported
# against its expected value (two tests at ≈ 5 % each → ≈ 10 %, and the lags are correlated, so a bit less).
rng = np.random.default_rng(7)
z0, z1 = (T0 - T0.mean()) / T0.std(), (T1 - T1.mean()) / T1.std()


def planted(z: np.ndarray, rho: float) -> np.ndarray:
    return 19 + 4.5 * (rho * z + np.sqrt(1 - rho ** 2) * rng.standard_normal(52))


res = {}
for name, make in (("lag0", lambda: planted(z0, 0.6)), ("lag1", lambda: planted(z1, 0.6)),
                   ("independent", lambda: 19 + 4.5 * rng.standard_normal(52))):
    finals = [link_rule(make(), T0, T1)[-1] for _ in range(200)]
    res[name] = {"flagged": round(sum(f["link"] == "link" for f in finals) / 200, 3),
                 "lag_named_right": round(sum(f["lag"] == (1 if name == "lag1" else 0) for f in finals
                                              if f["link"] == "link") / max(1, sum(f["link"] == "link" for f in finals)), 3)}
print("planted series at 52 weeks:", res)
assert res["lag0"]["flagged"] >= 0.95 and res["lag1"]["flagged"] >= 0.95, "power below 95 %"
assert res["independent"]["flagged"] <= 0.15, "false rate far above the stated ≈ 10 %"
print("✅ Phase 4 validation passed.")

# %% Phase 5 — Validator V10 on planted sentences (plan §3f part 3)
# A sentence relating billing to Suez traffic / the news: a cause word is always refused; "moves with" needs
# context.link cited with link = 'link'. News lines and figures side by side are not claims and pass.
from pipelines.agents.deck import validator as v2  # noqa: E402  (after the read-only phases)


def ev_with(verdict: str | None) -> dict:
    return {"context.link": {"tool": "finance_kpi", "status": "ok",
                             "source": {"kind": "view", "name": "finance.kpi_traffic_link"},
                             "rows": [{"report_week": 30, "link": verdict}]}}


CITE = ["context.link"]
PLANTED = [   # (text, cited, verdict) — every one must be refused
    ("Billing fell because of lower Suez transits", CITE, "link"),
    ("Revenue reflects the Red Sea disruption and weaker canal traffic", [], "link"),
    ("PortPilot billing dropped due to the news of Houthi attacks", CITE, "no_link"),
    ("Billing moved with Suez transits so far this year", CITE, "no_link"),
    ("Billing moved with Suez transits so far this year", [], "link"),
    ("Invoices tracked canal traffic closely", CITE, None),
    ("Billing was driven by Suez transits", CITE, "link"),
    ("Lower transits explain the drop in billing", CITE, "link"),
]
CLEAN = [     # (text, cited, verdict) — every one must pass V10
    ("Billing moved with Suez transits so far this year", CITE, "link"),
    ("Houthi attacks led to rerouting around the Cape of Good Hope", [], "no_link"),       # a news line: no billing word
    ("Billing was 2.93 M SDR; Suez transits averaged 35.6 a day", CITE, "no_link"),        # side by side, no relation
    ("There is no measurable link between billing and Suez transits this year", CITE, "no_link"),
]
caught = [t for t, c, vd in PLANTED if v2.link_problems(t, c, ev_with(vd))]
false_refusals = [t for t, c, vd in CLEAN if v2.link_problems(t, c, ev_with(vd))]
print(f"V10 planted sentences caught: {len(caught)} / {len(PLANTED)}; clean sentences refused: {false_refusals}")
assert len(caught) == len(PLANTED) and not false_refusals
print("✅ Phase 5 validation passed.")

# %% Final Checkpoint
final = {"datasets": len(DATASETS), "mismatches": len(mismatch), "live_link": actual["live_link_weeks"],
         "scenario_link_at_52": actual["scenario_link_at_52"], "power_ok": True, "v10_caught": len(caught)}
assert final == {"datasets": 3, "mismatches": 0, "live_link": 0, "scenario_link_at_52": True, "power_ok": True,
                 "v10_caught": 8}
print(f"✅ Final Checkpoint passed. False rate on independent series: {res['independent']['flagged']}")
