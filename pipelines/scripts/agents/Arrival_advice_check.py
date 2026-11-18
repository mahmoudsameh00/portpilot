"""Arrival advice check (JIT arrival plan §3e): the RTA store, the arrival arithmetic, the graph, the watch, the supervisor.

Plan:    docs/archive/2026-11-15_JIT_arrival_plan.md (approved and closed 2026-11-15; §2a D-J1…D-J3, §7 D-J8).
Run:     uv run python tools/run.py pipelines/scripts/agents/Arrival_advice_check.py              (Phases 1–7: 0 model calls)
         $env:EVAL_REAL_MODELS = '1'; uv run python tools/run.py pipelines/scripts/agents/Arrival_advice_check.py   (+ Phase 8)

Reads:   PostgreSQL read-only (vessels, port_call_messages, the migration 020 tables through the tools), MongoDB AIS
         (read-only user), the reference CSVs (vessel_performance, bunker_prices), the generator's CSV + manifest, the
         voyage file, the NOAA harbour profile, searoute locally. Open-Meteo / PortWatch: a mock transport in Phases 5–7,
         the real (cached) services in Phase 8.
Writes:  Data/processed/agents/eval/arrival_cases.json on its first run only (frozen; later runs assert it); check
         threads `arrival_advice:…` in agent_state, deleted at the end.
Re-run:  safe.

Phases
1. The RTA store (D-J1): the table = the generator's CSV; the RTA known at a clock = the latest message sent at or
   before it (revisions, cancellations, before the first message); the berth plan drawn from the schedule, never the
   true arrival; a probe user refused.
2. The arithmetic on 20 frozen cases = an independent computation (floats from the reference CSVs); 20 planted errors
   in the code results, all caught by the comparison.
3. Properties on a grid (live vessels × RTA offsets): JIT fuel ≤ keep fuel, JIT arrival = the target, the floor, the
   rule's choice, wait and late never both, waiting grows with a later RTA, the Cape only when the floor waits.
4. The Validator: planted errors in model text all caught, the good advices pass, the justified overrides.
4s. The skill arrival-advice: budgets, the examples render.
5. The graph on FakeRoles + the PostgreSQL checkpointer: ok, patch, validation_failed, output_invalid, on_time / late
   with no model call, not_at_sea, not_destination, no_rta, not_permitted, the Cape, weather down, a storm override,
   crash + resume with no tool call repeated.
6. The watch (D-J3): rta_late / jit alerts = the independent computation; the brief Validator over them; the clock rule.
7. The supervisor: the router (JIT questions → arrival_advice; no golden item changes route), the product tool's rows,
   the answer check binding its slots, RBAC.
8. The real model (EVAL_REAL_MODELS=1): 8 advices pass the Validator; two supervisor questions (EN + AR); one watch
   brief over arrival alerts.
"""
# %% Setup
import json
import math
import os
import re
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
import pandas as pd

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from pipelines.agents import checkpointer, roles, skill_loader  # noqa: E402
from pipelines.agents.deck import slots  # noqa: E402
from pipelines.agents.graphs import arrival_advice as aa  # noqa: E402
from pipelines.agents.graphs import models as m  # noqa: E402
from pipelines.agents.graphs import supervisor as sv  # noqa: E402
from pipelines.agents.graphs import voyage_watch as vw  # noqa: E402
from pipelines.agents.graphs.models import ArrivalRequest  # noqa: E402
from pipelines.agents.tools import arrival, context, db, eta, external, registry, voyages, watch  # noqa: E402
from pipelines.lib.common import load_env  # noqa: E402
from pipelines.lib.retrieval import User  # noqa: E402

load_env(ROOT)
REAL = os.environ.get("EVAL_REAL_MODELS") == "1"
CASES_FILE = ROOT / "Data" / "processed" / "agents" / "eval" / "arrival_cases.json"
CSV = ROOT / "Data" / "processed" / "synthetic" / "port_calls" / "port_call_messages.csv"
MANIFEST = ROOT / "Data" / "processed" / "synthetic" / "port_calls" / "manifest.json"
ASOF = context.DATA_AS_OF
OPS = context.load_user(2)                       # an Operations manager (the watch's identity, P11-8)
PROBE = User(0, "probe", 0, "Nowhere")           # below every ceiling, no department
VOY = voyages.voyages()
STATUS_CACHE: dict[int, dict] = {}


def status_row(vid: int) -> dict:
    if vid not in STATUS_CACHE:
        STATUS_CACHE[vid] = voyages.voyage_status(OPS, as_of=ASOF, vessel_id=vid).rows[0]
    return STATUS_CACHE[vid]


in_transit = [int(v) for v in VOY.index if status_row(int(v))["status_at_as_of"] == "In Transit"]
print(f"vessels in transit at the clock: {len(in_transit)}")

# %% Phase 1 — The RTA store (D-J1)
csv = pd.read_csv(CSV)
dbm = pd.DataFrame(db.fetch("SELECT message_id, vessel_id, voyage_no, port_locode, location, requested_time, sent_at, "
                            "message_status, sender, real_or_synthetic FROM port_call_messages ORDER BY message_id"))
for c in ("requested_time", "sent_at"):
    dbm[c] = pd.to_datetime(dbm[c], utc=True)
    csv[c] = pd.to_datetime(csv[c], utc=True)
csv = csv.sort_values("message_id").reset_index(drop=True)
same = all((dbm[c].astype(str) == csv[c].astype(str)).all() for c in
           ("message_id", "vessel_id", "voyage_no", "port_locode", "location", "requested_time", "sent_at",
            "message_status", "sender", "real_or_synthetic"))
assert len(dbm) == len(csv) == 680 and same, "the table differs from the generator's CSV"


def latest(vid: int, clock: pd.Timestamp) -> dict | None:
    """The independent rule: the last message of the call sent at or before the clock; cancelled → None."""
    rows = csv[(csv.vessel_id == vid) & (csv.sent_at <= clock)].sort_values(["sent_at", "message_id"])
    if rows.empty or rows.iloc[-1].message_status == "cancelled":
        return None
    return rows.iloc[-1].to_dict()


revised = csv.groupby("vessel_id").filter(lambda g: len(g) == 2 and (g.message_status == "requested").all())
cancelled = csv[csv.message_status == "cancelled"]
probes, agree = [], 0
for vid in sorted(set(revised.vessel_id))[:20] + sorted(set(cancelled.vessel_id))[:10]:
    msgs = csv[csv.vessel_id == vid].sort_values("sent_at")
    dest, vno = arrival.vessel_call(vid)
    for clock in (msgs.sent_at.iloc[0] - pd.Timedelta(minutes=1), msgs.sent_at.iloc[0],
                  msgs.sent_at.iloc[-1] - pd.Timedelta(minutes=1), msgs.sent_at.iloc[-1]):
        got = arrival.rta_known(OPS, vid, dest, vno, clock.to_pydatetime())
        want = latest(vid, clock)
        ok = (got.status == "no_data" and want is None) or (
            got.status == "ok" and want is not None and got.rows[0]["message_id"] == want["message_id"]
            and got.rows[0]["rta_utc"] == arrival.iso(want["requested_time"]))
        probes.append(ok)
assert all(probes), f"{probes.count(False)} RTA probes disagree"
assert arrival.rta_known(PROBE, 28, *arrival.vessel_call(28), ASOF).status == "not_permitted"
# the berth plan is drawn from the declared schedule, never from the true arrival (P9-7)
man = json.loads(MANIFEST.read_text(encoding="utf-8"))
sched = VOY.departure_ts + pd.to_timedelta(VOY.route_nm / VOY.service_kn, unit="h")
first = csv.sort_values("sent_at").groupby("vessel_id").first()
off_h = ((first.requested_time - sched.loc[first.index]).dt.total_seconds() / 3600)
inside = sum(man["scenarios"][man["scenario_by_vessel"][str(v)]]["offset_h"][0] - 0.5 <= off_h[v]
             <= man["scenarios"][man["scenario_by_vessel"][str(v)]]["offset_h"][1] + 0.5 for v in first.index)
assert inside == 500, f"{500 - inside} first RTAs outside their scenario's range around the schedule"
known_now = sum(latest(v, pd.Timestamp(ASOF)) is not None for v in in_transit)
actual_1 = {"messages": len(csv), "probes": len(probes), "first_rta_in_range": inside, "in_transit_with_rta": known_now}
REVIEWED_1 = {"messages": 680, "probes": 120, "first_rta_in_range": 500, "in_transit_with_rta": 44}
assert actual_1 == REVIEWED_1, actual_1
print(f"Phase 1: {actual_1}")
print("✅ Phase 1 validation passed: the table = the generator's CSV; the RTA at a clock = the latest message sent at "
      "or before it (revisions, cancellations, before the first); drawn from the schedule; a probe user refused")

# %% Phase 2 — The arithmetic on 20 frozen cases = an independent computation
# Case rule (frozen on the first run): 1–6 the lowest-id vessels at sea whose stored RTA gives `jit`; 7–8 `floor`;
# 9–11 late; 12 on time; 13–14 the two lowest-id vessels with the canal ahead and an RTA given far enough that the
# floor waits, so the Cape is compared (RTA = the last fix + the distance left at 8 kn + 5 days); 15–16 cases 1–2 at
# the pilot boarding place; 17–18 an RTA given = R + 6 h, 19 = R − 10 h and 20 = R + 1 h for the lowest-id vessels
# at sea without a stored RTA.
VP = pd.read_csv(ROOT / "db" / "reference" / "vessel_performance.csv")
BP = pd.read_csv(ROOT / "db" / "reference" / "bunker_prices.csv").iloc[-1]
VESSELS = pd.read_csv(ROOT / "Data" / "processed" / "synthetic" / "vessels.csv")
VESSELS.index = VESSELS.index + 1                 # vessel_id = the row number (the generator's order)
PRICE = round(BP.price_usd_per_t / BP.usd_per_sdr, 2)
HARBOUR = round(float(json.loads(eta.NOAA_PROFILE.read_text(encoding="utf-8"))["profile"]["implied_kn_moving"]["0.5"]), 1)


def r_eta(vid: int) -> pd.Timestamp:
    s = status_row(vid)
    return pd.Timestamp(eta.eta_rule(s, float(VOY.at[vid, "service_kn"]))["eta_utc"])


def stored_rule(vid: int) -> str | None:
    d = aa.deterministic(OPS, ArrivalRequest(vessel_id=vid), ASOF, with_context=False)
    if "arrival.summary" not in d["evidence"]:
        return None
    s = d["evidence"]["arrival.summary"]["rows"][0]
    return "late" if s["situation"] == "late" else ("on_time" if s["situation"] == "on_time" else s["rule_option"])


def build_cases() -> list[dict]:
    kinds = {v: stored_rule(v) for v in in_transit}
    pick = lambda k, n: [v for v in sorted(kinds) if kinds[v] == k][:n]  # noqa: E731
    out = [{"vessel_id": v, "rta_utc": None, "location": "berth", "kind": k}
           for k, n in (("jit", 6), ("floor", 2), ("late", 3), ("on_time", 1)) for v in pick(k, n)]
    ahead = [v for v in in_transit if eta.suez_ahead(v, status_row(v)["distance_covered_nm"])][:2]
    # the Cape cases: an RTA 5 days after even 8 kn would arrive (the floor is ≥ 8 kn → it waits → the Cape is compared)
    out += [{"vessel_id": v, "rta_utc": arrival.iso(pd.Timestamp(status_row(v)["last_fix"]["ts"]) + pd.Timedelta(
        hours=status_row(v)["distance_left_nm"] / 8 + 120)), "location": "berth", "kind": "cape"}
        for v in ahead]
    for c in out[:2]:
        rta = arrival.rta_known(OPS, c["vessel_id"], *arrival.vessel_call(c["vessel_id"]), ASOF).rows[0]["rta_utc"]
        out.append({"vessel_id": c["vessel_id"], "rta_utc": rta, "location": "pilot_boarding_place", "kind": "pbp"})
    free = [v for v in in_transit if kinds[v] is None and v not in ahead][:4]
    for v, h, k in zip(free, (6, 6, -10, 1), ("given_early", "given_early", "given_late", "given_on_time")):
        out.append({"vessel_id": v, "rta_utc": arrival.iso(r_eta(v) + pd.Timedelta(hours=h)), "location": "berth",
                    "kind": k})
    return [{"case": i + 1, **c} for i, c in enumerate(out)]


if CASES_FILE.exists():
    CASES = json.loads(CASES_FILE.read_text(encoding="utf-8"))["cases"]
    assert CASES == build_cases(), "the frozen cases no longer follow their rule (data changed?)"
else:
    CASES = build_cases()
    CASES_FILE.write_text(json.dumps({"rule": "JIT arrival plan §3e: see Arrival_advice_check.py Phase 2", "cases": CASES},
                                     indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{CASES_FILE.relative_to(ROOT).as_posix()}: written (frozen)")
assert len(CASES) == 20


def request(c: dict) -> ArrivalRequest:
    rta = datetime.fromisoformat(c["rta_utc"].replace("Z", "+00:00")) if c["rta_utc"] else None
    return ArrivalRequest(vessel_id=c["vessel_id"], rta_utc=rta, location=c["location"])


def band(vid: int) -> pd.Series:
    v = VESSELS.loc[vid]
    b = VP[(VP.vessel_type == v.vessel_type) & (VP.scnt_min <= v.scnt_tons)
           & (VP.scnt_max.isna() | (v.scnt_tons < VP.scnt_max))]
    assert len(b) == 1
    return b.iloc[0]


def rnd(x: float, n: int) -> float:
    q = 10 ** n
    return math.floor(abs(x) * q + 0.5 + 1e-9) / q * (1 if x >= 0 else -1)


def independent(c: dict, ev: dict) -> dict:
    """The arrival options from the plan's text, in floats, from the reference CSVs and the status row."""
    vid, s = c["vessel_id"], ev["arrival.status"]["rows"][0]
    b, svc = band(vid), float(VOY.at[vid, "service_kn"])
    ref, main, aux = float(b.ref_speed_kn), float(b.main_t_per_day), float(b.aux_t_per_day)
    v_now = rnd(float(s["recent_sog_kn"]) if s["recent_sog_kn"] and s["distance_covered_nm"] >= 20 else svc, 2)
    floor = min(max(8.0, rnd(ref * 0.5, 2)), v_now)
    cap = max(svc, v_now)
    rta_row = ev["arrival.rta"]["rows"][0]
    rta = pd.Timestamp(rta_row["rta_utc"])
    berth = rta_row["location"] == "berth"
    d_left = float(s["distance_left_nm"])
    appr = min(10.0, d_left)
    ah = appr / HARBOUR
    sea = d_left - appr
    t0 = pd.Timestamp(s["last_fix"]["ts"])
    target = rta - pd.Timedelta(hours=2)
    avail = ((target - pd.Timedelta(hours=ah if berth else 0)) - t0).total_seconds() / 3600
    toll = ev.get("arrival.toll")
    dues = float(toll["rows"][0]["amount_sdr"]) if toll and toll["status"] == "ok" else 0.0
    cape = [r for r in (ev.get("arrival.cape_route") or {}).get("rows") or []]

    def opt(name, v, sea_nm, dist, with_dues):
        v = rnd(v, 2)
        sea_h = sea_nm / v if sea_nm > 0 else 0.0
        ready = t0 + pd.Timedelta(hours=sea_h + (ah if berth else 0))
        wait = max((target - ready).total_seconds() / 3600, 0.0)
        late = max((ready - rta).total_seconds() / 3600, 0.0)
        pd_t = rnd(main * (v / ref) ** 3 + aux, 2)
        fuel = rnd(sea_h / 24 * pd_t, 1) + rnd(wait / 24 * aux, 1)
        sdr = rnd(fuel * PRICE, 2)
        return {"option": name, "speed_kn": v, "distance_nm": dist, "sea_h": sea_h, "arrival": ready, "wait_h": wait,
                "late_h": late, "fuel_t": fuel, "fuel_sdr": sdr, "total_sdr": sdr + (dues if with_dues else 0.0),
                "ok": late == 0 and floor - 0.005 <= v <= cap + 0.005, "allowed": floor - 0.005 <= v <= cap + 0.005}

    cape_on = bool(cape)
    rows = [opt("keep", v_now, sea, d_left, cape_on)]
    keep = rows[0]
    if keep["wait_h"] > 0 and sea > 0 and avail > 0:
        situation = "early"
        vj = sea / avail
        if vj >= floor:
            rows.append(opt("jit", min(vj, v_now), sea, d_left, cape_on))
        else:
            rows.append(opt("floor", floor, sea, d_left, cape_on))
            if cape_on:
                c_sea = float(cape[0]["distance_nm"]) - appr
                rows.append(opt("cape", min(max(c_sea / avail, floor), cap), c_sea, float(cape[0]["distance_nm"]),
                                False))
    elif keep["late_h"] > 0:
        situation = "late"
        if sea > 0 and cap > v_now:
            rows.append(opt("catch_up", min(max(sea / avail if avail > 0 else cap, v_now), cap), sea, d_left, cape_on))
    else:
        situation = "on_time"
    order = arrival.OPTIONS.index
    good = [r for r in rows if r["ok"]]
    pool = good or [r for r in rows if r["allowed"]] or rows
    rule = min(pool, key=lambda r: ((0, round(r["total_sdr"], 2)) if good else (round(r["late_h"], 1),
                                                                               round(r["total_sdr"], 2)))
               + (order(r["option"]),))
    return {"situation": situation, "rule": rule["option"], "options": rows, "floor": floor}


def compare(code: dict, ind: dict) -> list[str]:
    """Differences between the code's results and the independent computation (empty = they agree)."""
    out = []
    s = code["arrival.summary"]["rows"][0]
    if s["situation"] != ind["situation"]:
        out.append(f"situation {s['situation']} != {ind['situation']}")
    if s["rule_option"] != ind["rule"]:
        out.append(f"rule {s['rule_option']} != {ind['rule']}")
    if abs(s["floor_speed_kn"] - ind["floor"]) > 0.011:
        out.append(f"floor {s['floor_speed_kn']} != {ind['floor']}")
    got = {r["option"]: r for r in code["arrival.options"]["rows"]}
    if list(got) != [r["option"] for r in ind["options"]]:
        return out + [f"options {list(got)} != {[r['option'] for r in ind['options']]}"]
    for r in ind["options"]:
        g = got[r["option"]]
        tol = {"speed_kn": 0.011, "sea_h": 0.06, "wait_h": 0.06, "late_h": 0.06, "fuel_t": 0.21, "distance_nm": 0.051}
        for k, t in tol.items():
            if abs(float(g[k]) - float(r[k])) > t:
                out.append(f"{r['option']}.{k} {g[k]} != {round(float(r[k]), 3)}")
        # money: exactly the option's own tonnes × the reference price (rounded once), + the dues
        if abs(float(g["fuel_sdr"]) - rnd(float(g["fuel_t"]) * PRICE, 2)) > 0.011:
            out.append(f"{r['option']}.fuel_sdr {g['fuel_sdr']} != {g['fuel_t']} t × {PRICE}")
        if abs(float(g["total_sdr"]) - float(g["fuel_sdr"]) - (float(r["total_sdr"]) - float(r["fuel_sdr"]))) > 0.011:
            out.append(f"{r['option']}.total_sdr {g['total_sdr']} != fuel + dues")
        if abs((pd.Timestamp(g["arrival_utc"]) - r["arrival"]).total_seconds()) > 60:
            out.append(f"{r['option']}.arrival_utc {g['arrival_utc']} != {arrival.iso(r['arrival'])}")
    return out


EV = {c["case"]: aa.deterministic(OPS, request(c), ASOF, with_context=False)["evidence"] for c in CASES}
IND = {c["case"]: independent(c, EV[c["case"]]) for c in CASES}
diffs = {k: compare(EV[k], IND[k]) for k in EV}
assert not any(diffs.values()), {k: v for k, v in diffs.items() if v}
kinds = {c["case"]: c["kind"] for c in CASES}
rules = {k: EV[k]["arrival.summary"]["rows"][0]["rule_option"] for k in EV}
situations = {k: EV[k]["arrival.summary"]["rows"][0]["situation"] for k in EV}
assert all(rules[k] == "jit" for k in range(1, 7)) and all(rules[k] == "floor" for k in (7, 8))
assert all(situations[k] == "late" for k in (9, 10, 11)) and situations[12] == "on_time"
assert all("arrival.cape_route" in EV[k] and any(o["option"] == "cape" for o in EV[k]["arrival.options"]["rows"])
           for k in (13, 14))
# planted errors in the code results: one field of one option moved per case → the comparison flags every one
PLANT = [("speed_kn", 0.1), ("wait_h", 0.5), ("fuel_t", 1.0), ("fuel_sdr", 100.0), ("arrival_utc", 30), ("late_h", 0.5),
         ("total_sdr", 100.0), ("sea_h", 0.5)]
caught = 0
for i, k in enumerate(sorted(EV)):
    f, d = PLANT[i % len(PLANT)]
    bad = json.loads(json.dumps(EV[k]))
    row = bad["arrival.options"]["rows"][i % len(bad["arrival.options"]["rows"])]
    row[f] = (arrival.iso(pd.Timestamp(row[f]) + pd.Timedelta(minutes=d)) if f == "arrival_utc" else row[f] + d)
    caught += bool(compare(bad, IND[k]))
actual_2 = {"cases": len(CASES), "options": sum(len(EV[k]["arrival.options"]["rows"]) for k in EV),
            "rules": dict(sorted(__import__("collections").Counter(rules.values()).items())), "planted_caught": caught}
# reviewed 2026-11-15: 38 options; the rule picks jit 10, keep 5 (on time / late with no faster speed, or late with a
# catch-up that saves nothing), floor 3, cape 1 (case 13 or 14: round the Cape at a speed that fits beats the floor
# + waiting), catch_up 1
REVIEWED_2 = {"cases": 20, "options": 38, "rules": {"cape": 1, "catch_up": 1, "floor": 3, "jit": 10, "keep": 5},
              "planted_caught": 20}
assert actual_2 == REVIEWED_2, actual_2
print(f"Phase 2: {actual_2}; kinds {kinds}")
print("✅ Phase 2 validation passed: 20 cases = the independent computation (options, speeds, times, waits, fuel, "
      "SDR, the rule's choice); 20 / 20 planted result errors caught")

# %% Phase 3 — Properties on a grid (live vessels at sea × RTA offsets around R)
OFFSETS_H = (-24, -6, -1, 1, 3, 6, 24, 72, 240, 720)
grid_vessels = in_transit[::4][:40]
viol, n_opts, n_cases = [], 0, 0
for vid in grid_vessels:
    s = status_row(vid)
    base = r_eta(vid)
    waits = []
    for h in OFFSETS_H:
        rta = (base + pd.Timedelta(hours=h)).to_pydatetime()
        d = aa.deterministic(OPS, ArrivalRequest(vessel_id=vid, rta_utc=rta), ASOF, with_context=False)
        if "arrival.options" not in d["evidence"]:
            continue
        n_cases += 1
        o = {r["option"]: r for r in d["evidence"]["arrival.options"]["rows"]}
        sm = d["evidence"]["arrival.summary"]["rows"][0]
        n_opts += len(o)
        target = pd.Timestamp(sm["target_utc"])
        if "jit" in o:
            j = o["jit"]
            if j["fuel_t"] > o["keep"]["fuel_t"]:
                viol.append((vid, h, "jit fuel > keep fuel"))
            tol_h = j["sea_h"] * 0.006 / j["speed_kn"] + 0.02
            if abs((pd.Timestamp(j["arrival_utc"]) - target).total_seconds() / 3600) > tol_h + 1 / 60:
                viol.append((vid, h, "jit arrival != target"))
            if j["speed_kn"] < sm["floor_speed_kn"] - 0.005:
                viol.append((vid, h, "jit below the floor"))
        if "floor" in o and (abs(o["floor"]["speed_kn"] - sm["floor_speed_kn"]) > 0.005 or o["floor"]["wait_h"] <= 0):
            viol.append((vid, h, "floor speed / wait"))
        if sm["floor_speed_kn"] > sm["current_speed_kn"] or (sm["floor_speed_kn"] < 8 and
                                                            sm["floor_speed_kn"] != sm["current_speed_kn"]):
            viol.append((vid, h, "floor rule"))
        for r in o.values():
            if r["wait_h"] > 0 and r["late_h"] > 0:
                viol.append((vid, h, f"{r['option']} waits and is late"))
        on_time = [r for r in o.values() if r["arrives_by_rta"] and r["speed_allowed"]]
        if on_time and not o[sm["rule_option"]]["arrives_by_rta"]:
            viol.append((vid, h, "the rule chose a late option while one is on time"))
        if on_time and o[sm["rule_option"]]["total_sdr"] > min(r["total_sdr"] for r in on_time):
            viol.append((vid, h, "the rule is not the cheapest on-time option"))
        if "cape" in o and "floor" not in o:
            viol.append((vid, h, "cape without floor"))
        waits.append(sm["keep_wait_h"])
    if any(b < a for a, b in zip(waits, waits[1:])):
        viol.append((vid, None, "keep wait falls with a later RTA"))
assert not viol, viol[:10]
print(f"Phase 3: {n_cases} grid cases on {len(grid_vessels)} vessels, {n_opts} options, 0 property violations")
print("✅ Phase 3 validation passed: JIT fuel ≤ keep, JIT at the target, the floor, the rule's choice, wait / late "
      "exclusive, waiting monotone in the RTA, the Cape only with the floor")

# %% Phase 4 — The Validator: planted errors in model text
def good_advice(ev: dict) -> dict:
    s = ev["arrival.summary"]["rows"][0]
    rule = s["rule_option"]
    if s["situation"] == "late":
        return {"recommendation": rule, "headline": f"Keep sailing: the berth is missed by {{arrival.options[{rule}]:late_h}}.",
                "reasons": [{"text": f"At {{arrival.options[{rule}]:speed_kn}} the vessel reaches the berth after the "
                                     f"requested time {s['rta_utc']}.", "evidence_ids": ["arrival.options"]}],
                "risks": []}
    return {"recommendation": rule,
            "headline": f"Sail at {{arrival.options[{rule}]:speed_kn}} to arrive just in time.",
            "reasons": [{"text": f"At {{arrival.options[{rule}]:speed_kn}} the vessel uses {{arrival.options[{rule}]:fuel_t}}"
                                 f" of fuel instead of {{arrival.options[keep]:fuel_t}}.",
                         "evidence_ids": ["arrival.options"]},
                        {"text": f"Keeping the speed means waiting {{arrival.summary:keep_wait_h}} at anchor before "
                                 f"{s['rta_utc']}.", "evidence_ids": ["arrival.summary"]}],
            "risks": []}


def plants(ev: dict) -> list[dict]:
    g = good_advice(ev)
    names = [r["option"] for r in ev["arrival.options"]["rows"]]
    other = next(n for n in names if n != g["recommendation"])
    missing = next(n for n in arrival.OPTIONS if n not in names)
    out = []
    for f in (lambda a: a.update(headline=a["headline"] + " That saves about 160 t."),
              lambda a: a["reasons"][0].update(text=a["reasons"][0]["text"] + " It is 12 hours early."),
              lambda a: a["reasons"][0].update(text=a["reasons"][0]["text"] + " Berth on 2026-10-30."),
              lambda a: a["reasons"][0]["evidence_ids"].append("arrival.news"),
              lambda a: a["reasons"][0].update(evidence_ids=["arrival.summary"]),
              lambda a: a.update(recommendation=other),
              lambda a: a.update(recommendation=missing),
              lambda a: a["reasons"][0].update(text=a["reasons"][0]["text"] + " {arrival.options[keep]:co2_t}."),
              lambda a: a["reasons"][0].update(text=a["reasons"][0]["text"] + " {arrival.options[fast]:speed_kn}."),
              lambda a: a["risks"].append({"text": "Winds near 40 knots on the way.", "evidence_ids": []}),
              # D-J8: a change slot after "saves" reads as a double negative ("saves −160.5 t")
              lambda a: a["reasons"][0].update(text=a["reasons"][0]["text"] + " That saves "
                                               f"{{arrival.options[{a['recommendation']}]:change_fuel_t}}."),
              # D-J8: an arrival time named as the RTA (the keep arrival is never the RTA in these cases)
              lambda a, ev=ev: a["reasons"][0].update(text=a["reasons"][0]["text"] + " Its RTA is "
                                                      f"{ev['arrival.summary']['rows'][0]['keep_arrival_utc']}.")):
        a = json.loads(json.dumps(g))
        f(a)
        out.append(a)
    return out


p4_cases = [1, 7, 9, 13, 17]
false_alarms = [k for k in EV if aa.validate(good_advice(EV[k]), EV[k])]
assert not false_alarms, {k: aa.validate(good_advice(EV[k]), EV[k]) for k in false_alarms}
planted = [(k, i, aa.validate(a, EV[k])) for k in p4_cases for i, a in enumerate(plants(EV[k]))]
missed = [(k, i) for k, i, p in planted if not p]
assert not missed, missed
# a justified override: keep instead of jit when the first reason cites a storm on the next legs / a Suez drop
ev1 = json.loads(json.dumps(EV[1]))
ov = good_advice(ev1) | {"recommendation": "keep"}
ov["reasons"] = [{"text": "Keep the speed to pass ahead of the storm on the next legs.",
                  "evidence_ids": ["arrival.weather"]}] + ov["reasons"]
ev1["arrival.weather"] = arrival.result("arrival_risks", [{"kind": "weather", "severity": "high", "date": "2026-09-14",
                                                           "wave_height_max_m": 7.0, "wind_speed_10m_max_kn": 50.0}],
                                        "planted")
over_ok = not aa.validate(ov, ev1)
ev1["arrival.weather"]["rows"] = []
over_no_row = bool(aa.validate(ov, ev1))
ov_t = json.loads(json.dumps(ov))
ov_t["reasons"][0]["evidence_ids"] = ["arrival.traffic"]
for pct, want_ok in ((-25.0, True), (-10.0, False)):
    ev1["arrival.traffic"] = arrival.result("route_costs", [{"route": "traffic", "change_transits_pct": pct}], "planted")
    assert (not aa.validate(ov_t, ev1)) == want_ok, (pct, aa.validate(ov_t, ev1))
assert over_ok and over_no_row
print(f"Phase 4: {len(planted)} planted errors caught ({len(p4_cases)} cases × {len(planted) // len(p4_cases)}), 0 false alarms on 20 good "
      "advices; overrides: a storm row / Suez −25 % pass, no row / −10 % refused")
print("✅ Phase 4 validation passed.")

# %% Phase 4s — The skill arrival-advice
sk = skill_loader.catalog()["arrival-advice"]
assert sk.stage == "2" and 20 <= len(sk.description) <= skill_loader.DESCRIPTION_MAX
assert sk.body_tokens <= skill_loader.BODY_MAX_TOKENS
examples = re.findall(r"\{arrival\.[^{}]+\}", sk.body)
ev_ex = json.loads(json.dumps(EV[1]))
ev_ex["arrival.options"]["rows"] += [r for r in EV[7]["arrival.options"]["rows"] if r["option"] == "floor"]
rendered = [slots.render_text(x, ev_ex) for x in examples]
assert all(not e for _, _, e in rendered), [e for _, _, e in rendered if e]
print(f"Phase 4s: skill body {sk.body_tokens} tokens; {len(examples)} example slots render; reviewed_by_owner = "
      f"{sk.reviewed_by_owner}")
print("✅ Phase 4s validation passed.")

# %% Phase 5 — The graph on FakeRoles + the PostgreSQL checkpointer
mock = {"weather": "calm", "portwatch": "ok", "requests": 0}


def fake_http(req: httpx.Request) -> httpx.Response:
    mock["requests"] += 1
    p = req.url.params
    if "arcgis" in req.url.host:
        if mock["portwatch"] == "down":
            return httpx.Response(500, text="down")
        start = date.fromisoformat(re.search(r"date >= DATE '([\d-]+)'", p["where"]).group(1))
        n = 40 if start.year == 2025 else 30
        return httpx.Response(200, json={"features": [{"attributes": {
            "date": (start + timedelta(days=k)).isoformat(), "n_total": n, "n_container": 10, "n_tanker": 8,
            "n_dry_bulk": 6, "n_general_cargo": 3, "n_roro": 1, "capacity": 1_000_000}} for k in range(28)]})
    if mock["weather"] == "down":
        return httpx.Response(500, text="down")
    lats = [float(x) for x in p["latitude"].split(",")]
    d0, d1 = date.fromisoformat(p["start_date"]), date.fromisoformat(p["end_date"])
    days = [(d0 + timedelta(days=k)).isoformat() for k in range((d1 - d0).days + 1)]
    wave, wind = (7.0, 50.0) if mock["weather"] == "storm" else (1.0, 10.0)
    body = []
    for _ in lats:
        if "marine" in req.url.host:
            daily = {"wave_height_max": [wave] * len(days), "swell_wave_height_max": [wave] * len(days),
                     "wind_wave_height_max": [wave] * len(days)}
        else:
            daily = {"wind_speed_10m_max": [wind] * len(days), "wind_gusts_10m_max": [wind] * len(days)}
        body.append({"daily": {"time": days, **daily}})
    return httpx.Response(200, json=body)


script_mode = {"m": "good", "calls": 0}


def digest_evidence(messages) -> dict:
    text = "\n".join(str(x.content) for x in messages)
    s = json.loads(re.search(r"\[arrival\.summary\] (\{.*\})", text).group(1))
    opts = [json.loads(x) for x in re.findall(r"\[arrival\.options\] (\{.*\})", text)]
    return {"arrival.summary": {"rows": [s]}, "arrival.options": {"rows": opts}}


def script(role, messages, tools, schema):
    script_mode["calls"] += 1
    md = script_mode["m"]
    patching = any("Code checked your ArrivalAdvice" in str(x.content) for x in messages)
    if md == "crash":
        script_mode["m"] = "good"
        raise RuntimeError("simulated crash in the advisor")
    if md == "invalid":
        return {"recommendation": "jit", "reasons": []}
    adv = good_advice(digest_evidence(messages))
    if md == "override":
        adv["recommendation"] = "keep"
        adv["reasons"].insert(0, {"text": "Keep the speed to pass ahead of the storm on the next legs.",
                                  "evidence_ids": ["arrival.weather"]})
    if md == "always_bad" or (md == "patch" and not patching):
        adv["headline"] += " That is about 160 t."
    return adv


tmp_cache = Path(tempfile.mkdtemp(prefix="arrival_cache_"))
real_http, real_today = external.HTTP, external.TODAY
PACE = (vw.LOCATIONS_PER_MIN, vw.RETRY_WAIT_S)
vw.LOCATIONS_PER_MIN, vw.RETRY_WAIT_S = None, 0
saver = checkpointer.saver()
threads: list[str] = []


def fresh_caches(tag: str) -> None:
    for name in ("marine_weather", "suez_transits"):
        external._caches[name] = external.ExternalCache(name, tmp_cache / tag)


def run(g, req: ArrivalRequest, mode: str = "good", user=OPS, thread: str | None = None, resume: bool = False):
    script_mode["m"] = mode
    tid = thread or aa.new_thread_id(checkpointer.pool(), user.employee_id, ASOF, req.vessel_id)
    if tid not in threads:
        threads.append(tid)
    cfg = {"configurable": {"thread_id": tid}}
    g.invoke(None if resume else {"request": req.model_dump(mode="json")}, cfg, context=context.RunContext(user),
             durability="sync")
    return tid, g.get_state(cfg).values


anchored = min(int(v) for v in VOY.index if status_row(int(v))["status_at_as_of"] == "Anchored")
no_rta = CASES[16]["vessel_id"]
late_single = next((k for k in (9, 10, 11) if len(EV[k]["arrival.options"]["rows"]) == 1), None)
try:
    external.HTTP = httpx.Client(transport=httpx.MockTransport(fake_http), timeout=external.TIMEOUT_S)
    external.TODAY = date(2026, 11, 15)
    fresh_caches("calm")
    g = aa.build_graph(roles.FakeRoles(script), saver)
    res5, calls5 = {}, {}
    for c in CASES:
        before = script_mode["calls"]
        _, st = run(g, request(c))
        res5[c["case"]], calls5[c["case"]] = st["result"], script_mode["calls"] - before
    st_all = {k: r["status"] for k, r in res5.items()}
    single = {k for k in EV if len(EV[k]["arrival.options"]["rows"]) == 1}
    assert all(st_all[k] in ("on_time", "late") and calls5[k] == 0 for k in single), (st_all, calls5)
    assert all(st_all[k] == "ok" and calls5[k] == 1 and res5[k]["recommendation"] == rules[k]
               for k in EV if k not in single), (st_all, calls5)
    assert all(res5[k]["options"] == EV[k]["arrival.options"]["rows"] for k in EV), "numbers changed in the graph"
    assert all(not re.search(r"\{arrival", res5[k]["headline"] or "") for k in EV)
    assert any("Cape option" in a for a in res5[13]["assumptions"])
    _, st_p = run(g, request(CASES[0]), "patch")
    _, st_b = run(g, request(CASES[0]), "always_bad")
    _, st_i = run(g, request(CASES[0]), "invalid")
    assert st_p["result"]["status"] == "ok" and st_p["patches"] == 1
    assert st_b["result"]["status"] == "validation_failed" and st_b["result"]["problems"]
    assert st_i["result"]["status"] == "output_invalid"
    stops = {"not_at_sea": run(g, ArrivalRequest(vessel_id=anchored))[1]["result"]["status"],
             "not_destination": run(g, ArrivalRequest(vessel_id=CASES[0]["vessel_id"], port="ZZZZZ"))[1]["result"]
             ["status"],
             "no_rta": run(g, ArrivalRequest(vessel_id=no_rta))[1]["result"]["status"],
             "not_permitted": run(g, request(CASES[0]), user=PROBE)[1]["result"]["status"]}
    assert stops == {k: k for k in stops}, stops
    mock["weather"] = "down"
    fresh_caches("down")
    _, st_d = run(g, request(CASES[1]))
    assert st_d["result"]["status"] == "ok" and any("Weather context unavailable" in a for a in st_d["result"]["assumptions"])
    mock["weather"] = "storm"
    fresh_caches("storm")
    _, st_o = run(g, request(CASES[2]), "override")
    assert st_o["result"]["status"] == "ok" and st_o["result"]["recommendation"] == "keep", st_o["result"]
    mock["weather"] = "calm"
    fresh_caches("calm")
    req_c = request(CASES[3])
    tid = aa.new_thread_id(checkpointer.pool(), OPS.employee_id, ASOF, req_c.vessel_id)
    crashed = False
    try:
        run(g, req_c, "crash", thread=tid)
    except RuntimeError:
        crashed = True
    http_before = mock["requests"]
    _, st_r = run(g, req_c, "good", thread=tid, resume=True)
    assert crashed and st_r["result"]["status"] == "ok" and mock["requests"] == http_before
    pref = aa.thread_prefix(OPS.employee_id, ASOF, CASES[0]["vessel_id"])
    nxt = aa.new_thread_id(checkpointer.pool(), OPS.employee_id, ASOF, CASES[0]["vessel_id"])
    assert nxt.startswith(pref) and int(nxt.rsplit(":", 1)[1]) > max(
        int(t.rsplit(":", 1)[1]) for t in threads if t.startswith(pref))           # the next free number
    assert aa.thread_owner(tid) == OPS.employee_id
finally:
    external.HTTP, external.TODAY = real_http, real_today
    for name in ("marine_weather", "suez_transits"):
        external._caches.pop(name, None)
    for t in threads:
        saver.delete_thread(t)
actual_5 = {"statuses": dict(sorted(__import__("collections").Counter(st_all.values()).items())),
            "model_calls": sum(calls5.values()), "stops": sorted(stops), "threads_deleted": len(threads)}
print(f"Phase 5: {actual_5}; patch / validation_failed / output_invalid / weather down / storm override / crash + "
      "resume (0 HTTP repeated)")
print("✅ Phase 5 validation passed.")

# %% Phase 6 — The watch (D-J3)
try:
    external.HTTP = httpx.Client(transport=httpx.MockTransport(fake_http), timeout=external.TIMEOUT_S)
    external.TODAY = date(2026, 11, 15)
    fresh_caches("watch")
    det = vw.deterministic(OPS, ASOF)
finally:
    external.HTTP, external.TODAY = real_http, real_today
    for name in ("marine_weather", "suez_transits"):
        external._caches.pop(name, None)
al = det["evidence"]["watch.alerts"]["rows"]
fleet = det["evidence"]["watch.fleet"]["rows"][0]
mine = {a["alert_id"]: a for a in al if a["kind"] in ("rta_late", "jit")}
want = {}
for vid in in_transit:
    if latest(vid, pd.Timestamp(ASOF)) is None:
        continue
    d = aa.deterministic(OPS, ArrivalRequest(vessel_id=vid), ASOF, with_context=False)["evidence"]
    ind = independent({"vessel_id": vid}, d)
    keep = ind["options"][0]
    if ind["situation"] == "late":
        want[f"{vid}/rta_late"] = "high" if rnd(keep["late_h"], 1) >= vw.RTA_LATE_HIGH_H else "moderate"
    elif ind["situation"] == "early" and rnd(keep["wait_h"], 1) >= vw.JIT_WAIT_H and ind["rule"] in ("jit", "floor"):
        want[f"{vid}/jit"] = "moderate"
assert {k: a["severity"] for k, a in mine.items()} == want, (sorted(set(mine) ^ set(want)))
assert fleet["rta_known_vessels"] >= len(want) and fleet["jit_alerts"] + fleet["rta_late_alerts"] == len(mine)
an = [r for r in det["etas"] if r["status"] == "Anchored" and r["rta_utc"]]
assert all("berth requested for" in r["note"] for r in an)
# the brief Validator over the arrival alerts
jid = next(k for k in mine if k.endswith("/jit"))
lid = next(k for k in mine if k.endswith("/rta_late") and mine[k]["severity"] == "high")
ev6 = det["evidence"]
highs = [a["alert_id"] for a in al if a["severity"] == "high"]
brief = {"headline": "{watch.fleet:jit_alerts} vessels can slow down for their berth.",
         "items": [{"text": f"Slow to {{watch.alerts[{jid}]:jit_speed_kn}} instead of waiting {{watch.alerts[{jid}]:wait_h}}"
                            f" for the berth at {mine[jid]['rta_utc']}.", "alert_ids": [jid]},
                   {"text": "These vessels will miss their requested arrival.", "alert_ids": highs[:60]}]}
m.WatchBrief.model_validate(brief)
assert not vw.validate(brief, ev6), vw.validate(brief, ev6)
bad = json.loads(json.dumps(brief))
bad["items"][0]["text"] += " It saves 160 t."
bad2 = json.loads(json.dumps(brief))
bad2["items"][0]["text"] = bad2["items"][0]["text"].replace(mine[jid]["rta_utc"], "2026-12-01T10:00Z")
assert vw.validate(bad, ev6) and vw.validate(bad2, ev6)
# the clock rule: a week earlier no RTA sent later than that clock is read
early_clock = ASOF - timedelta(days=7)
early_rows = [r.rows[0] for v in in_transit[:60]
              if (r := voyages.voyage_status(OPS, as_of=early_clock, vessel_id=v)).status == "ok"]
r_e = [vw._rta(OPS, row) for row in early_rows]
assert all(r is None or pd.Timestamp(r["sent_at"]) <= pd.Timestamp(early_clock) for r in r_e)
print(f"Phase 6: {len(mine)} arrival alerts ({sum(a['kind'] == 'jit' for a in mine.values())} jit, "
      f"{sum(a['kind'] == 'rta_late' for a in mine.values())} rta_late, "
      f"{sum(a['severity'] == 'high' for a in mine.values())} high) = the independent computation; "
      f"{len(an)} anchored vessels show their RTA; the brief Validator passes a cited brief and refuses a typed "
      "number / a foreign date")
print("✅ Phase 6 validation passed.")

# %% Phase 6w — The watch makes the advice (Arrival advice web plan, owner 2026-11-17)
# Every jit / rta_late alert of the watch gets its arrival advice in the same run (`vw.advise_arrivals`, the `arrival`
# node). On fake models (a writer that never answers): what code decides is there, the written part stops calmly.
# What must hold for the alert and its advice to never disagree in front of a user: the advice's own computation (the
# rule's option, its speed; late → the catch-up speed) = the alert's figures, at the same clock.
silent = roles.FakeRoles(lambda role, msgs, tools, schema: {})
try:
    external.HTTP = httpx.Client(transport=httpx.MockTransport(fake_http), timeout=external.TIMEOUT_S)
    external.TODAY = date(2026, 11, 15)
    fresh_caches("watch_arrivals")
    ctx6 = context.RunContext(OPS, as_of=ASOF)
    arrivals6, usage6 = vw.advise_arrivals(silent, ctx6, al)

    class _Boom:                                         # a model that breaks: one advice fails, the watch goes on
        def get(self, role):
            raise RuntimeError("provider down")
    two = sorted(mine.values(), key=lambda a: a["vessel_id"])[:2]
    broken, _ = vw.advise_arrivals(_Boom(), ctx6, two)
finally:
    external.HTTP, external.TODAY = real_http, real_today
    for name in ("marine_weather", "suez_transits"):
        external._caches.pop(name, None)
alerted6 = {str(a["vessel_id"]) for a in mine.values()}
assert set(arrivals6) == alerted6, sorted(set(arrivals6) ^ alerted6)
agree = 0
for a in mine.values():
    adv = arrivals6[str(a["vessel_id"])]
    s = adv["summary"]
    assert adv["alert_id"] == a["alert_id"] and adv["options"], (a["alert_id"], adv.get("status"), adv.get("problems"))
    by_opt = {o["option"]: o for o in adv["options"]}
    if a["kind"] == "jit":
        assert s["rule_option"] == a["jit_option"], (a["alert_id"], s["rule_option"], a["jit_option"])
        assert by_opt[a["jit_option"]]["speed_kn"] == a["jit_speed_kn"], (a["alert_id"], by_opt[a["jit_option"]])
        assert by_opt[a["jit_option"]]["change_fuel_t"] == a["change_fuel_t"], a["alert_id"]
    else:
        assert s["situation"] == "late" and s["keep_late_h"] == a["late_h"], (a["alert_id"], s)
        if a.get("catch_up_speed_kn") is not None:
            assert by_opt["catch_up"]["speed_kn"] == a["catch_up_speed_kn"], a["alert_id"]
    assert s["rta_utc"] == a["rta_utc"], (a["alert_id"], s["rta_utc"], a["rta_utc"])
    assert adv["status"] in ("late", "on_time", "output_invalid"), (a["alert_id"], adv["status"])
    agree += 1
written = sum(adv["status"] == "output_invalid" for adv in arrivals6.values())
assert len(broken) == len(two) and all(
    (b["status"] == "error" and "provider down" in b["problems"][0]) or b["status"] in ("late", "on_time")
    for b in broken.values()), broken
# the run file keeps the advice; the alert reader hands it out with its own alert only
tmp6 = Path(tempfile.mkdtemp(prefix="watch_arrivals_"))
tid6 = "voyage_watch:20260913T0000Z:7"
vw.write_run_file(tmp6, tid6, {"status": "ok", "as_of": ASOF.isoformat(), "alerts": al, "arrivals": arrivals6,
                               "brief_status": None, "headline": None})
read6 = watch.read_alerts(OPS, folder=tmp6)
with_adv = [x for x in read6["alerts"] if "advice" in x]
assert {x["alert_id"] for x in with_adv} == set(mine) and all(x["kind"] in vw.ARRIVAL_KINDS for x in with_adv)
assert all(x["advice"]["alert_id"] == x["alert_id"] for x in with_adv)
print(f"Phase 6w: the watch advised {len(arrivals6)} vessels = its {len(mine)} jit / rta_late alerts; the advice's own "
      f"computation = the alert's option, speed, fuel change, lateness and RTA on all {agree}; {written} wait for the "
      f"writer (stopped calmly on the silent fake), the rest decided by code; a breaking model fails its advice only; "
      f"the run file keeps them and the alert reader attaches each to its own alert")
print("✅ Phase 6w validation passed.")

# %% Phase 7 — The supervisor: router, the product tool, the answer check, RBAC
GOLD = [json.loads(x) for x in (ROOT / "Data" / "processed" / "agents" / "eval" / "supervisor_qa_golden.jsonl")
        .read_text(encoding="utf-8").splitlines() if x.strip()]
assert not [g_["id"] for g_ in GOLD if "arrival" in sv.route(g_["question"], OPS).matched]
JIT_Q = ["Vessel 28 has a berth at its destination at 2026-09-18T22:30Z: what speed should it sail?",
         "Should vessel 36 slow down for its RTA?", "Just in time arrival for vessel 38: keep speed or slow steam?",
         "المركب 28 يهدي السرعة عشان ميعاد الرصيف؟", "المركب 100 لازم يمشي بسرعة كام عشان يلحق الرصيف؟"]
assert all("arrival_advice" in sv.route(q, OPS).tools for q in JIT_Q), [sv.route(q, OPS).tools for q in JIT_Q]
assert "arrival_advice" in [t.name for t in registry.supervisor_tools(roles.FakeRoles(script))]
assert "arrival_advice" not in sv.route(JIT_Q[0], PROBE).tools and "arrival_advice" in sv.route(JIT_Q[0], PROBE).refused
threads7: list[str] = []
try:
    external.HTTP = httpx.Client(transport=httpx.MockTransport(fake_http), timeout=external.TIMEOUT_S)
    external.TODAY = date(2026, 11, 15)
    fresh_caches("sup")
    script_mode["m"] = "good"
    tr = registry.ARRIVAL_ADVICE(OPS, roles.FakeRoles(script), as_of=ASOF, saver=saver, vessel_id=CASES[0]["vessel_id"])
    tr_given = registry.ARRIVAL_ADVICE(OPS, roles.FakeRoles(script), as_of=ASOF, saver=saver,
                                       vessel_id=CASES[16]["vessel_id"], rta_utc=CASES[16]["rta_utc"])
    tr_stop = registry.ARRIVAL_ADVICE(OPS, roles.FakeRoles(script), as_of=ASOF, saver=saver, vessel_id=no_rta)
    threads7 = [r["thread_id"] for t_ in (tr, tr_given) for r in t_.rows if r["option"] == "advice"]
finally:
    external.HTTP, external.TODAY = real_http, real_today
    for name in ("marine_weather", "suez_transits"):
        external._caches.pop(name, None)
    with checkpointer.pool().connection() as conn:              # the stopped question's thread too
        stray = [r["thread_id"] for r in conn.execute(
            "SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id LIKE %s",
            (f"{aa.THREAD_PREFIX}{OPS.employee_id}:{ASOF.date().isoformat()}:{no_rta}:%",)).fetchall()]
    for t in threads7 + stray:
        saver.delete_thread(t)
    vw.LOCATIONS_PER_MIN, vw.RETRY_WAIT_S = PACE
shutil.rmtree(tmp_cache, ignore_errors=True)
keys = [r["option"] for r in tr.rows]
assert tr.status == "ok" and keys[-2:] == ["summary", "advice"] and keys[:-2] == [
    r["option"] for r in EV[1]["arrival.options"]["rows"]]
assert tr.rows[-1]["recommendation"] == rules[1] and tr_given.status == "ok" and tr_stop.status == "no_data"
ev7 = {"insight.c1": sv.model_view(tr.model_dump(mode="json"))}
ans = {"status": "answered", "answer": "Slow to {insight.c1[jit]:speed_kn}: the vessel would otherwise wait "
                                       "{insight.c1[summary]:keep_wait_h} at anchor."}
text7, bound7, problems7 = sv.check_supervisor_answer(ans, ev7, JIT_Q[1])
assert not problems7 and len(bound7) == 2 and "kn" in text7, (problems7, text7)
# D-J8 in the supervisor's check (only when the arrival tool is in the evidence): a double negative, a wrong RTA
summ7 = next(r for r in ev7["insight.c1"]["rows"] if r["option"] == "summary")
bad7 = [{"status": "answered", "answer": "Slow to {insight.c1[jit]:speed_kn}, saving {insight.c1[jit]:change_fuel_t}."},
        {"status": "answered", "answer": f"Slow to {{insight.c1[jit]:speed_kn}} for its RTA at {summ7['target_utc']}."}]
assert all(sv.check_supervisor_answer(b, ev7, JIT_Q[1])[2] for b in bad7)
assert "assumptions" not in ev7["insight.c1"]["rows"][-1]
print(f"Phase 7: router {len(JIT_Q)} / {len(JIT_Q)} JIT questions (EN + AR) → arrival_advice, 0 / {len(GOLD)} golden "
      f"items re-routed, refused to a probe user; the product tool's rows {keys}; the answer check binds 2 slots")
print("✅ Phase 7 validation passed.")

# %% Phase 8 — The real model (EVAL_REAL_MODELS=1)
if not REAL:
    print("Phase 8 skipped (set EVAL_REAL_MODELS=1 for the real model)")
    print("✅ Final Checkpoint: Phases 1–7 passed with 0 model calls; Phase 8 pending (real model)")
    raise SystemExit(0)
# Provider probe first (a few tiny calls, Model_probe.py) is run by hand before this phase. The `writer` role (ADR-045,
# llm.py: cached, quota-aware) writes the advice of the first 8 cases with a choice; the bar of ADR-057: every advice
# passes the Validator (possibly after its one patch). Then two supervisor questions (EN + AR) on the `tools` role and
# one voyage-watch brief over the arrival alerts of a few vessels (a small weather request). Real Open-Meteo and
# PortWatch through the tools' cache. Every thread is a check thread, deleted at the end.
from pipelines.agents.graphs.models import WatchRequest  # noqa: E402

real_roles = roles.Roles()
g8 = aa.build_graph(real_roles, saver)
threads8: list[str] = []
real_cases = [c for c in CASES if c["case"] not in single][:8]
res8 = {}
try:
    for c in real_cases:
        tid = aa.new_thread_id(checkpointer.pool(), OPS.employee_id, ASOF, c["vessel_id"])
        threads8.append(tid)
        cfg = {"configurable": {"thread_id": tid}}
        g8.invoke({"request": request(c).model_dump(mode="json")}, cfg, context=context.RunContext(OPS),
                  durability="sync")
        st = g8.get_state(cfg).values
        u = st.get("llm_usage") or []
        res8[c["case"]] = {"status": st["result"]["status"], "recommendation": st["result"]["recommendation"],
                           "rule": rules[c["case"]], "patches": st.get("patches", 0), "calls": len(u),
                           "cached": sum(bool(x.get("cached")) for x in u),
                           "models": sorted({x.get("model") for x in u if x.get("model")}),
                           "headline": st["result"]["headline"], "problems": st["result"]["problems"][:2]}
        print(c["case"], {k: v for k, v in res8[c["case"]].items() if k != "headline"})
        print("   ", res8[c["case"]]["headline"])
    sg = sv.build_graph(real_roles, saver)
    sup8 = {}
    for q, tag in ((f"Vessel {CASES[0]['vessel_id']} has a berth at its destination: should it slow down for its RTA?",
                    "en"), (f"المركب {CASES[1]['vessel_id']} يهدي السرعة عشان ميعاد الرصيف ولا يكمل بسرعته؟", "ar")):
        tid = f"ask:{OPS.employee_id}:arrival_check:{tag}"
        threads8.append(tid)
        st = sv.ask(sg, q, OPS, as_of=ASOF, thread=tid)
        u = st.get("llm_usage") or []
        sup8[tag] = {"status": st["status"], "routed": st["routed"], "calls": len(u),
                     "cited_arrival": any((st.get("evidence") or {}).get(b["eid"], {}).get("tool") == "arrival_advice"
                                          for b in st.get("bound") or []), "answer": st.get("rendered")}
        print(tag, {k: v for k, v in sup8[tag].items() if k != "answer"})
        print("   ", (sup8[tag]["answer"] or "")[:400])
    vids = sorted({int(k.split("/")[0]) for k in list(mine)[:6]})
    tmp_rep = Path(tempfile.mkdtemp(prefix="arrival_watch_real_"))
    gw = vw.build_graph(real_roles, saver, tmp_rep)
    tidw = vw.new_thread_id(checkpointer.pool(), ASOF, "voyage_watch_check:")
    threads8.append(tidw)
    gw.invoke({"request": WatchRequest(vessel_ids=vids).model_dump(mode="json")}, {"configurable": {"thread_id": tidw}},
              context=context.RunContext(OPS), durability="sync")
    rw = gw.get_state({"configurable": {"thread_id": tidw}}).values["result"]
    shutil.rmtree(tmp_rep, ignore_errors=True)
    watch8 = {"brief": rw["brief_status"], "alerts": [a["alert_id"] for a in rw["alerts"]],
              "items": [i["text"] for i in rw.get("items") or []][:4], "headline": rw.get("headline")}
    print("watch", watch8)
finally:
    # + the arrival threads the supervisor's tool opened for the two questions (its own thread per call)
    with checkpointer.pool().connection() as conn:
        threads8 += [r["thread_id"] for r in conn.execute(
            "SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id LIKE %s",
            (f"{aa.THREAD_PREFIX}{OPS.employee_id}:{ASOF.date().isoformat()}:%",)).fetchall()]
    for t in dict.fromkeys(threads8):
        saver.delete_thread(t)
passed = sum(r["status"] == "ok" for r in res8.values())
print(f"Phase 8: {passed} / {len(res8)} real advices passed the Validator "
      f"({sum(r['patches'] for r in res8.values())} patches, {sum(r['calls'] for r in res8.values())} calls, "
      f"{sum(r['cached'] for r in res8.values())} cached); recommendations = the rule in "
      f"{sum(r['recommendation'] == r['rule'] for r in res8.values())}; supervisor "
      f"{ {k: v['status'] for k, v in sup8.items()} }; watch brief {watch8['brief']}")
assert passed == len(res8) == 8, res8
assert all(v["status"] == "answered" and "arrival_advice" in v["routed"] for v in sup8.values()), sup8
assert watch8["brief"] == "ok", watch8
print("✅ Phase 8 validation passed.")
print("✅ Final Checkpoint: Phases 1–8 passed (real model 8 / 8)")
