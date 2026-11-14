"""Finance scenario generator — the 2025 invoices re-dated so that weekly billing follows real Suez traffic, with a
stated, planted amplification (traffic-billing link plan Phase 2, `docs/plans/Traffic_billing_link_plan.md` §3b',
owner decision D-TL-3: "a stronger planted link, labelled").

Reads:   PostgreSQL read-only (PG_RO_USER): public.invoices, public.payments, and the definitions and comments of the
         finance views to twin (pg_get_viewdef with an empty search_path, so every name comes back schema-qualified).
         Data/processed/structured/suez_transits_daily.csv (Suez_transits_loader.py; = external.suez_transits_daily).
Writes:  Data/processed/synthetic/finance_scenario_invoices.csv, finance_scenario_payments.csv,
         finance_scenario_manifest.json, db/migrations/026_finance_scenario.sql (schema finance_scenario: the re-dated
         tables, scenario_info, and twins of eight finance views; applied by the owner or by the assistant on his word).
Safe to re-run: yes — fixed seeds; the same database gives byte-identical files. After 026 is applied, Phase 7 checks
         the scenario views against an independent pandas reference (before that it reports "pending").
Run:     uv run python tools/run.py pipelines/scripts/synthetic/Finance_scenario_generator.py
"""
# %% Phase 0 — Setup
# The scenario keeps every invoice (amount, vessel, customer, category) and every payment delay; only the timing moves.
# Weekly weights = mean + α × (transits − mean): α = 1 is "billing follows traffic exactly" (the natural scenario,
# detected 66 % of the time at 52 weeks — loader manifest); α is the smallest factor that makes the link rule
# (|r| ≥ 2 / √n, n = 52) fire in ≥ 95 % of seeded draws. α is written into the schema, a table and every comment.
import datetime as dt
import hashlib
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import psycopg

# The script's own folder, not the project root, is on sys.path when it is run by path (tools/run.py).
sys.path.insert(0, str(next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists())))
from pipelines.lib.common import load_env, project_root

ROOT = project_root()
load_env(ROOT)
SYN = ROOT / "Data" / "processed" / "synthetic"
TRANSITS = ROOT / "Data" / "processed" / "structured" / "suez_transits_daily.csv"
INV_CSV, PAY_CSV = SYN / "finance_scenario_invoices.csv", SYN / "finance_scenario_payments.csv"
MANIFEST = SYN / "finance_scenario_manifest.json"
MIGRATION = ROOT / "db" / "migrations" / "026_finance_scenario.sql"
WEEK1_MONDAY, HISTORY_START, WEEK52_SUNDAY = dt.date(2024, 12, 30), dt.date(2025, 1, 1), dt.date(2025, 12, 28)
SEED_ALPHA, SEED_DRAW, DRAWS, TARGET = 42, 43, 2000, 0.95
ALPHA_GRID = [round(1 + 0.1 * k, 1) for k in range(41)]          # 1.0 … 5.0
TWINS = ["fact_invoice", "fact_payment", "fact_ar_snapshot", "kpi_customer_13w", "kpi_overdue_list", "kpi_weekly",
         "kpi_weekly_category", "kpi_weekly_trend"]                # dependency order (information_schema usage)
SCHEMA = "finance_scenario"


def pg():
    e = os.environ
    return psycopg.connect(host=e["PGHOST"], port=e["PGPORT"], dbname=e["PGDATABASE"], user=e["PG_RO_USER"],
                           password=e["PG_RO_PASSWORD"], options="-c default_transaction_read_only=on",
                           connect_timeout=5)


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lit(v) -> str:
    """A SQL literal for one value."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "NULL"
    if isinstance(v, (int, Decimal)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def week_of(d: dt.date) -> int:
    return (d - WEEK1_MONDAY).days // 7 + 1


# %% Phase 1 — Inputs (read-only)
with pg() as conn:
    inv_cols = [r[0] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'invoices' "
        "ORDER BY ordinal_position")]
    invoices = [dict(zip(inv_cols, r)) for r in conn.execute("SELECT * FROM public.invoices ORDER BY invoice_id")]
    payments = [dict(zip(("invoice_number", "paid_date", "amount_sdr"), r)) for r in conn.execute(
        "SELECT invoice_number, paid_date, amount_sdr FROM public.payments ORDER BY invoice_number")]
    conn.execute("SET search_path = ''")
    view_sql = {v: conn.execute("SELECT pg_get_viewdef(%s::regclass, true)", (f"finance.{v}",)).fetchone()[0]  # type: ignore[index]
                for v in TWINS}
    view_comment = {v: conn.execute("SELECT obj_description(%s::regclass, 'pg_class')",
                                    (f"finance.{v}",)).fetchone()[0]  # type: ignore[index]
                    for v in TWINS}
    col_comments = {v: conn.execute(
        "SELECT a.attname, col_description(a.attrelid, a.attnum) FROM pg_attribute a "
        "WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum",
        (f"finance.{v}",)).fetchall()
        for v in TWINS}
    scenario_exists = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = %s)", (SCHEMA,)).fetchone()[0]  # type: ignore[index]

transits = pd.read_csv(TRANSITS)
weekly_t: dict[int, int] = {}
for d_, n_ in zip(transits["date"], transits["n_total"]):
    wk_ = week_of(dt.date.fromisoformat(str(d_)))
    if 1 <= wk_ <= 52:
        weekly_t[wk_] = weekly_t.get(wk_, 0) + int(n_)
T = np.array([weekly_t[w] for w in range(1, 53)], dtype=float)
in_weeks = [i for i in invoices if HISTORY_START <= i["invoice_date"] <= WEEK52_SUNDAY]
snapshot = {"invoices": 1000, "payments": 994, "invoices_weeks_1_52": 996, "transit_weeks": 52, "twins": 8}
actual = {"invoices": len(invoices), "payments": len(payments), "invoices_weeks_1_52": len(in_weeks),
          "transit_weeks": len(T), "twins": len(view_sql)}
assert actual == snapshot, actual
print(f"inputs: {actual}; finance_scenario exists: {scenario_exists}")
print("✅ Phase 1 validation passed.")

# %% Phase 2 — α: the smallest planted amplification that the link rule detects ≥ 95 % of the time at 52 weeks
mean = float(T.mean())
alpha_max = mean / (mean - float(T.min()))                        # beyond it a week's weight would be ≤ 0
thr52 = 2 / np.sqrt(52)


def weights(a: float) -> np.ndarray:
    w = mean + a * (T - mean)
    return w / w.sum()


rng = np.random.default_rng(SEED_ALPHA)
rates: dict[float, float] = {}
for a in ALPHA_GRID:
    if a >= alpha_max:
        break
    c = rng.multinomial(len(in_weeks), weights(a), size=DRAWS).astype(float)
    r = np.array([np.corrcoef(x, T)[0, 1] for x in c])
    rates[a] = float((np.abs(r) >= thr52).mean())
ALPHA = next(a for a, rate in rates.items() if rate >= TARGET)
print("α grid → link rate at 52 weeks: " +", ".join(f"{a}: {rates[a]:.3f}" for a in list(rates)[:8]) + " …")
print(f"α = {ALPHA} (rate {rates[ALPHA]:.3f}; natural α = 1.0: {rates[1.0]:.3f}; α max {alpha_max:.2f})")
assert rates[1.0] < TARGET <= rates[ALPHA] and ALPHA < alpha_max
print("✅ Phase 2 validation passed.")

# %% Phase 3 — Draw the weekly counts and re-date the invoices
# One multinomial draw (seed 43) gives the count per week; a seeded permutation decides which invoices go to which
# week; inside a week the day is uniform over its days from 2025-01-01 on (no 2024 invoices: receivables start at 0).
# The 4 invoices of 2025-12-29 / 30 (ISO 2026-W01) keep their dates.
rng = np.random.default_rng(SEED_DRAW)
counts = rng.multinomial(len(in_weeks), weights(ALPHA))
order = rng.permutation(len(in_weeks))
new_date: dict[str, dt.date] = {}
k = 0
for wk, n in enumerate(counts, start=1):
    monday = WEEK1_MONDAY + dt.timedelta(days=7 * (wk - 1))
    days_ok = [monday + dt.timedelta(days=j) for j in range(7) if monday + dt.timedelta(days=j) >= HISTORY_START]
    for _ in range(int(n)):
        new_date[in_weeks[order[k]]["invoice_number"]] = days_ok[int(rng.integers(len(days_ok)))]
        k += 1
scen_inv = []
for i in invoices:
    row = dict(i)
    row["original_invoice_date"] = i["invoice_date"]
    row["invoice_date"] = new_date.get(i["invoice_number"], i["invoice_date"])
    scen_inv.append(row)

got = np.bincount([week_of(r["invoice_date"]) for r in scen_inv if r["invoice_date"] <= WEEK52_SUNDAY], minlength=53)[1:]
assert got.tolist() == counts.tolist() and k == len(in_weeks), "weekly counts differ from the draw"
assert all(r["invoice_date"] >= HISTORY_START for r in scen_inv), "a 2024 invoice"
same = [(r["invoice_number"], r["vessel_id"], r["amount"]) for r in scen_inv]
assert same == [(i["invoice_number"], i["vessel_id"], i["amount"]) for i in invoices], "amounts or vessels moved"
realized = {n: round(float(np.corrcoef(counts[:n].astype(float), T[:n])[0, 1]), 3) for n in (13, 26, 52)}
print(f"weekly counts min / max {counts.min()} / {counts.max()}; realized r: {realized} "
      f"(thresholds {2 / np.sqrt(13):.3f} / {2 / np.sqrt(26):.3f} / {thr52:.3f})")
assert realized[52] >= thr52, "this draw does not show the planted link at 52 weeks"
print("✅ Phase 3 validation passed.")

# %% Phase 4 — Payments keep their own delay
by_number = {r["invoice_number"]: r for r in scen_inv}
scen_pay = []
for p in payments:
    old_inv = by_number[p["invoice_number"]]["original_invoice_date"]
    delay = (p["paid_date"] - old_inv).days
    scen_pay.append({"invoice_number": p["invoice_number"], "amount_sdr": p["amount_sdr"],
                     "paid_date": by_number[p["invoice_number"]]["invoice_date"] + dt.timedelta(days=delay),
                     "original_paid_date": p["paid_date"]})
d_old = sorted((p["paid_date"] - by_number[p["invoice_number"]]["original_invoice_date"]).days for p in payments)
d_new = sorted((p["paid_date"] - by_number[p["invoice_number"]]["invoice_date"]).days for p in scen_pay)
assert d_old == d_new and len(scen_pay) == 994, "payment delays changed"
print(f"payments {len(scen_pay)}; delay min / median / max {d_new[0]} / {d_new[len(d_new) // 2]} / {d_new[-1]} days; "
      f"paid after 2025-12-28: {sum(p['paid_date'] > WEEK52_SUNDAY for p in scen_pay)}")
print("✅ Phase 4 validation passed.")

# %% Phase 5 — The migration: tables, scenario_info, twin views, comments, grants
label = f"Scenario (planted: α = {ALPHA} × the real 2025 Suez traffic swing) — not PortPilot's billing"
twin_re = re.compile(r"\bfinance\.(" + "|".join(sorted(TWINS, key=len, reverse=True)) + r")\b")
views = []
for v in TWINS:
    body = view_sql[v].strip().rstrip(";")
    body = body.replace("public.invoices", f"{SCHEMA}.invoices").replace("public.payments", f"{SCHEMA}.payments")
    body = twin_re.sub(lambda m: f"{SCHEMA}.{m.group(1)}", body)
    assert "public.invoices" not in body and "public.payments" not in body and not twin_re.search(body), v
    views.append(f"CREATE VIEW {SCHEMA}.{v} AS\n{body};\n"
                 f"COMMENT ON VIEW {SCHEMA}.{v} IS {lit(label + '. Twin of finance.' + v + ': ' + (view_comment[v] or ''))};\n"
                 + "".join(f"COMMENT ON COLUMN {SCHEMA}.{v}.{c} IS {lit(t)};\n" for c, t in col_comments[v] if t))

inv_out_cols = [*inv_cols, "original_invoice_date"]
inv_values = ",\n".join("(" + ", ".join(lit(r[c] if not isinstance(r[c], dt.date) else r[c].isoformat())
                                        for c in inv_out_cols) + ")" for r in scen_inv)
pay_values = ",\n".join(f"({lit(p['invoice_number'])}, '{p['paid_date']}', {p['amount_sdr']}, '{p['original_paid_date']}')"
                        for p in scen_pay)
sql = f"""-- 026_finance_scenario.sql — generated by pipelines/scripts/synthetic/Finance_scenario_generator.py (do not edit by hand)
-- Traffic-billing link plan Phase 2 (docs/plans/Traffic_billing_link_plan.md §3b'; owner decision D-TL-3).
-- {label}.
-- The 2025 invoices re-dated: weekly counts ~ Multinomial(996, mean + α(transits − mean)), seed {SEED_DRAW}; each payment
-- keeps its own delay. The live schema finance and its tables are untouched. Level 2 / Finance.
BEGIN;

CREATE SCHEMA {SCHEMA};
COMMENT ON SCHEMA {SCHEMA} IS {lit(label + '. Re-dated copies of invoices / payments and twins of the finance KPI views; for the link measure and its check only')};

CREATE TABLE {SCHEMA}.scenario_info (
    label            text    NOT NULL,
    alpha            numeric NOT NULL,
    seed_draw        integer NOT NULL,
    link_rate_52     numeric NOT NULL,
    natural_rate_52  numeric NOT NULL,
    realized_r_52    numeric NOT NULL,
    source           text    NOT NULL
);
COMMENT ON TABLE {SCHEMA}.scenario_info IS 'The one row that labels this scenario: its planted amplification and how it was chosen';
COMMENT ON COLUMN {SCHEMA}.scenario_info.label IS 'The label every scenario output must show';
COMMENT ON COLUMN {SCHEMA}.scenario_info.alpha IS 'Planted amplification of the weekly traffic swing (1 = billing follows traffic exactly)';
COMMENT ON COLUMN {SCHEMA}.scenario_info.seed_draw IS 'Seed of the multinomial draw, the permutation and the days';
COMMENT ON COLUMN {SCHEMA}.scenario_info.link_rate_52 IS 'Share of {DRAWS} seeded draws at this alpha where the link rule fires at 52 weeks';
COMMENT ON COLUMN {SCHEMA}.scenario_info.natural_rate_52 IS 'The same share at alpha = 1 (the natural scenario)';
COMMENT ON COLUMN {SCHEMA}.scenario_info.realized_r_52 IS 'Pearson r of this draw: weekly invoice count vs weekly Suez transits, weeks 1-52, lag 0';
COMMENT ON COLUMN {SCHEMA}.scenario_info.source IS 'Where the traffic comes from';
INSERT INTO {SCHEMA}.scenario_info VALUES ({lit(label)}, {ALPHA}, {SEED_DRAW}, {rates[ALPHA]:.3f}, {rates[1.0]:.3f}, {realized[52]}, 'external.suez_transits_daily (IMF PortWatch)');

CREATE TABLE {SCHEMA}.invoices (
    invoice_id            integer PRIMARY KEY,
    invoice_number        text    NOT NULL UNIQUE,
    vessel_id             integer NOT NULL REFERENCES public.vessels (vessel_id),
    toll_rate_band_id     integer REFERENCES public.toll_rate_bands (id),
    invoice_date          date    NOT NULL,
    scnt_tons             numeric,
    rate_sdr_per_ton      numeric,
    amount                numeric NOT NULL,
    description           text,
    status                text,
    original_invoice_date date    NOT NULL
);
COMMENT ON TABLE {SCHEMA}.invoices IS {lit(label + ': public.invoices with invoice_date re-dated')};
""" + "".join(f"COMMENT ON COLUMN {SCHEMA}.invoices.{c} IS {lit(t)};\n" for c, t in [
    ("invoice_id", "As in public.invoices"), ("invoice_number", "As in public.invoices"),
    ("vessel_id", "As in public.invoices"), ("toll_rate_band_id", "As in public.invoices"),
    ("invoice_date", "Scenario date: the re-dated invoice day"), ("scnt_tons", "As in public.invoices"),
    ("rate_sdr_per_ton", "As in public.invoices"), ("amount", "As in public.invoices (SDR)"),
    ("description", "As in public.invoices"), ("status", "As in public.invoices (a random label, never used)"),
    ("original_invoice_date", "The live invoice_date in public.invoices")]) + f"""
CREATE TABLE {SCHEMA}.payments (
    invoice_number     text    PRIMARY KEY REFERENCES {SCHEMA}.invoices (invoice_number),
    paid_date          date    NOT NULL,
    amount_sdr         numeric NOT NULL,
    original_paid_date date    NOT NULL
);
COMMENT ON TABLE {SCHEMA}.payments IS {lit(label + ': public.payments with paid_date moved by its invoice, the delay kept')};
COMMENT ON COLUMN {SCHEMA}.payments.invoice_number IS 'As in public.payments';
COMMENT ON COLUMN {SCHEMA}.payments.paid_date IS 'Scenario date: the new invoice date + the live delay';
COMMENT ON COLUMN {SCHEMA}.payments.amount_sdr IS 'As in public.payments (SDR)';
COMMENT ON COLUMN {SCHEMA}.payments.original_paid_date IS 'The live paid_date in public.payments';

INSERT INTO {SCHEMA}.invoices ({', '.join(inv_out_cols)}) VALUES
{inv_values};

INSERT INTO {SCHEMA}.payments (invoice_number, paid_date, amount_sdr, original_paid_date) VALUES
{pay_values};

""" + "\n".join(views) + f"""
GRANT USAGE ON SCHEMA {SCHEMA} TO ports_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA {SCHEMA} TO ports_readonly;

COMMIT;
"""
MIGRATION.write_text(sql, encoding="utf-8", newline="\n")
txt = MIGRATION.read_text(encoding="utf-8")
assert txt.count(f"CREATE VIEW {SCHEMA}.") == 8 and "public.invoices i" not in txt.split("CREATE VIEW", 1)[1]
print(f"wrote {MIGRATION.name} ({len(txt):,} chars, 8 twin views)")
print("✅ Phase 5 validation passed.")

# %% Phase 6 — CSV mirrors and manifest; reload and re-validate
pd.DataFrame(scen_inv)[inv_out_cols].to_csv(INV_CSV, index=False, lineterminator="\n")
pd.DataFrame(scen_pay)[["invoice_number", "paid_date", "amount_sdr", "original_paid_date"]].to_csv(
    PAY_CSV, index=False, lineterminator="\n")
back_i, back_p = pd.read_csv(INV_CSV), pd.read_csv(PAY_CSV)
assert len(back_i) == 1000 and len(back_p) == 994 and back_i["invoice_number"].is_unique
manifest: dict[str, Any] = {
    "plan": "docs/plans/Traffic_billing_link_plan.md (Phase 2, D-TL-3)", "label": label, "alpha": ALPHA,
    "alpha_rates_52": {str(a): round(r, 3) for a, r in rates.items()}, "seed_alpha": SEED_ALPHA,
    "seed_draw": SEED_DRAW, "draws": DRAWS, "weekly_counts": counts.tolist(), "realized_r": realized,
    "files": {p.relative_to(ROOT).as_posix(): sha256(p) for p in (INV_CSV, PAY_CSV, MIGRATION)}}
MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print("✅ Phase 6 validation passed.")

# %% Phase 7 — After 026 is applied: the scenario views = an independent pandas reference
# Billed, invoice count, collected, payments received, AR and overdue at each Sunday (docs/finance_metrics.md M1–M5),
# recomputed from the scenario tables without the views' SQL. Pending until the schema exists.
if not scenario_exists:
    print("Phase 7 pending: finance_scenario is not applied yet")
else:
    with pg() as conn:
        kw = pd.DataFrame(conn.execute(
            f"SELECT report_week, billed_sdr, invoices_billed, collected_sdr, payments_received, ar_sdr, overdue_sdr "
            f"FROM {SCHEMA}.kpi_weekly ORDER BY report_week").fetchall(),
            columns=["w", "billed", "n", "collected", "n_pay", "ar", "overdue"]).astype(float)
        terms = dict(conn.execute("SELECT v.vessel_id, c.payment_terms_days FROM public.vessels v "
                                  "JOIN public.customers c USING (customer_id)").fetchall())
        info = conn.execute(f"SELECT alpha, realized_r_52 FROM {SCHEMA}.scenario_info").fetchone()
    paid = {p["invoice_number"]: p for p in scen_pay}
    ref = []
    for wk in range(1, 53):
        mon = WEEK1_MONDAY + dt.timedelta(days=7 * (wk - 1))
        sun = mon + dt.timedelta(days=6)
        billed = [r for r in scen_inv if mon <= r["invoice_date"] <= sun]
        coll = [p for p in scen_pay if mon <= p["paid_date"] <= sun]
        open_ = [r for r in scen_inv if r["invoice_date"] <= sun
                 and (r["invoice_number"] not in paid or paid[r["invoice_number"]]["paid_date"] > sun)]
        over = [r for r in open_ if (sun - (r["invoice_date"] + dt.timedelta(days=terms[r["vessel_id"]]))).days >= 1]
        ref.append([wk, float(sum(r["amount"] for r in billed)), len(billed), float(sum(p["amount_sdr"] for p in coll)),
                    len(coll), float(sum(r["amount"] for r in open_)), float(sum(r["amount"] for r in over))])
    ref_df = pd.DataFrame(ref, columns=kw.columns)
    diff = (kw - ref_df).abs().max()
    print("max |view − reference|:", {k: round(float(v), 4) for k, v in diff.items()})
    assert float(diff[["n", "n_pay"]].max()) == 0 and float(diff[["billed", "collected", "ar", "overdue"]].max()) < 0.011
    assert info is not None and float(info[0]) == ALPHA and float(info[1]) == realized[52]
    print("✅ Phase 7 validation passed.")

# %% Final Checkpoint
# Narrative: pipelines/checkpoints/synthetic/Finance_scenario_generator.md
final = {"invoices": len(scen_inv), "payments": len(scen_pay), "weeks": len(counts), "twins": len(views),
         "alpha_found": ALPHA in rates, "link_at_52": realized[52] >= thr52}
assert final == {"invoices": 1000, "payments": 994, "weeks": 52, "twins": 8, "alpha_found": True,
                 "link_at_52": True}, final
print(f"✅ Final Checkpoint passed. α = {ALPHA}, realized r(52) = {realized[52]}")
