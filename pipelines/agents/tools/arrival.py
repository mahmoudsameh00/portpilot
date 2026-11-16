"""Just-in-Time arrival: the RTA known at the clock and the arrival options (JIT arrival plan §3b, §2a D-J1 / D-J3).

**The RTA** (Requested Time of Arrival) is a port-call message (`public.port_call_messages`, migration 030): the one
known at the clock is the latest message of the vessel's current port call (vessel + voyage number + destination)
with `sent_at <= as_of`; a cancelled latest message means the call has no RTA. The rule is the same for synthetic and
real messages. A question may give its own RTA instead (J1); it is marked `rta_source = question`.

**The options** (code only; exact Decimal, each shown figure rounded once, half away from zero). From a
`voyage_status` row at the clock and the vessel's `vessel_params` row:
- the open-sea part = the distance left minus the port approach (`eta.APPROACH_NM` at `eta.harbour_kn()`, rule R);
- the target = RTA − the margin (J3, 2 h) at the RTA's location: at the berth the approach hours come after the
  sea part; at the pilot boarding place the sea part ends there;
- **keep** = the current sea speed (R's), then wait at anchor until the target; **jit** = the speed that reaches the
  target exactly; when that speed is below the floor (J2: max(8 kn, 50 % of the band's IMO reference speed), never
  above the current speed) → **floor** = the floor, then wait the rest; when the vessel would miss the RTA →
  **catch_up** = the speed that makes the target, capped at the service speed (late when even that is not enough);
  **cape** (J4, only when the delay cannot be absorbed at the floor and the canal is ahead) = the remaining voyage
  from the vessel's position round the Cape at the speed that fits, the Suez dues saved.
- fuel: per sea day = main × (v / ref)³ + aux (the cube law of `vessel_params`), while waiting = aux per day; money
  = tonnes × the dated SDR price per tonne; the approach is the same in every option and is not priced.
- **the rule's choice** = the cheapest option that is at the location by the RTA; when none is, the least late, then
  the cheapest. The Validator of the graph holds the model to it unless a cited risk justifies another (J5).
"""
import re
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import cast

import pandas as pd

from pipelines.agents.tools import context, db, eta, routes, voyages
from pipelines.agents.tools.schemas import Source, ToolResult

FLOOR_MIN_KN = Decimal("8")          # J2: the lowest speed allowed …
FLOOR_SHARE = Decimal("0.5")         # … or this share of the band's IMO reference speed, whichever is higher
MARGIN_H = Decimal("2")              # J3: arrive this long before the RTA
OPTIONS = ("keep", "jit", "floor", "catch_up", "cape")
LOCATIONS = ("berth", "pilot_boarding_place")
CODE = "arrival (code)"
H = Decimal(3600)


def _d(x) -> Decimal:
    return Decimal(str(x))


def _q(x: Decimal, places: int) -> Decimal:
    return x.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def _f(x: Decimal, places: int) -> float:
    return float(_q(x, places))


def ts(s) -> pd.Timestamp:
    t = cast(pd.Timestamp, pd.Timestamp(s))            # never NaT here: every caller passes a real instant
    return t.tz_convert("UTC") if t.tzinfo else t.tz_localize("UTC")


def iso(t) -> str:
    return ts(t).isoformat(timespec="minutes").replace("+00:00", "Z")


def _hours(a, b) -> Decimal:
    """b − a in hours (exact to the second)."""
    return _d(int((ts(b) - ts(a)).total_seconds())) / H


# --- the RTA known at the clock -------------------------------------------------------------------------------------

def rta_known(user, vessel_id: int, port: str, voyage_no: str, as_of: datetime) -> ToolResult:
    """The latest RTA message of one port call sent at or before the clock (tool `port_call_messages`)."""
    if not context.permitted(user, context.PORT_CALLS):
        return context.denied("port_call_messages")
    msgs = db.fetch("SELECT message_id, location, requested_time, sent_at, message_status, sender, real_or_synthetic, "
                    "source FROM port_call_messages WHERE vessel_id = %s AND port_locode = %s AND voyage_no = %s "
                    "AND time_type = 'RTA' AND sent_at <= %s ORDER BY sent_at, message_id",
                    (vessel_id, port, voyage_no, as_of))
    flt = (f"vessel_id = {vessel_id}, voyage {voyage_no}, port {port}, sent_at <= {iso(pd.Timestamp(as_of))}; "
           "the latest message wins")
    src = Source(kind="table", name="public.port_call_messages", filter=flt)
    if not msgs:
        return ToolResult(tool="port_call_messages", status="no_data", source=src,
                          note=f"no RTA message for vessel {vessel_id} at {port} sent at or before "
                               f"{iso(pd.Timestamp(as_of))}")
    last = msgs[-1]
    if last["message_status"] == "cancelled":
        return ToolResult(tool="port_call_messages", status="no_data", source=src,
                          note=f"the RTA for vessel {vessel_id} at {port} was cancelled at {iso(last['sent_at'])} "
                               f"({last['message_id']})")
    row = {"vessel_id": vessel_id, "port": port, "voyage_no": voyage_no, "rta_utc": iso(last["requested_time"]),
           "location": last["location"], "message_id": last["message_id"], "sent_at": iso(last["sent_at"]),
           "sender": last["sender"], "real_or_synthetic": last["real_or_synthetic"],
           "revision_count": len(msgs) - 1, "rta_source": "port_call_messages"}
    return ToolResult(tool="port_call_messages", status="ok", rows=[row], source=src,
                      note="the RTA known at the clock: the latest message of the port call sent at or before it")


def rta_given(vessel_id: int, port: str, rta: datetime, location: str = "berth") -> ToolResult:
    """An RTA given in the question (CLI, supervisor): the same row shape, marked `rta_source = question`."""
    row = {"vessel_id": vessel_id, "port": port, "voyage_no": None, "rta_utc": iso(pd.Timestamp(rta)),
           "location": location, "message_id": None, "sent_at": None, "sender": None, "real_or_synthetic": None,
           "revision_count": 0, "rta_source": "question"}
    return ToolResult(tool="port_call_messages", status="ok", rows=[row],
                      source=Source(kind="library", name="the question", filter=f"RTA given for vessel {vessel_id}"),
                      note="the RTA given in the question (it wins over a stored port-call message)")


# --- the options ----------------------------------------------------------------------------------------------------

def floor_kn(params: dict) -> tuple[Decimal, str]:
    ref = _d(params["ref_speed_kn"])
    share = _q(ref * FLOOR_SHARE, 2)
    if share > FLOOR_MIN_KN:
        return share, f"50 % of the IMO reference speed {params['ref_speed_kn']} kn ({params['imo_ship_type']} " \
                      f"{params['imo_size_bin']})"
    return FLOOR_MIN_KN, f"the 8 kn minimum (50 % of the IMO reference speed {params['ref_speed_kn']} kn is lower)"


def per_day(params: dict, v: Decimal) -> Decimal:
    """Fuel t per sea day at v (the cube law of vessel_params, rounded like its fuel_t_per_day)."""
    ref, main, aux = _d(params["ref_speed_kn"]), _d(params["main_t_per_day_at_ref"]), _d(params["aux_t_per_day"])
    return _q(main * (v / ref) ** 3 + aux, 2)


def cape_path_nm(status: dict) -> tuple[float | None, list[str]]:
    """The remaining voyage from the last fix to the destination with the canal closed: (nm, passages) or None."""
    f = status["last_fix"]
    dest = routes.ports()[status["destination"]]
    p = routes.sea_path((f["lat"], f["lon"]), dest, (*routes.ALWAYS_CLOSED, "suez"))
    if p is None:
        return None, []
    return round(float(routes.line(p[0], p[1])["cum"][-1]), 1), p[2]


@dataclass(frozen=True)
class _Leg:
    """What every option of one question shares: the open-sea part, the clock, the RTA and the vessel's prices."""
    sea_nm: Decimal
    approach_h: Decimal
    t0: pd.Timestamp
    target: pd.Timestamp
    rta: pd.Timestamp
    at_berth: bool
    params: dict
    sdr_t: Decimal
    floor: Decimal
    cap: Decimal


def _option(name: str, v: Decimal, leg: _Leg, dues: Decimal, distance_nm: Decimal) -> dict:
    v = _q(v, 2)
    sea_h = leg.sea_nm / v if leg.sea_nm > 0 else Decimal(0)
    ready = ts(leg.t0) + pd.Timedelta(seconds=float((sea_h + (leg.approach_h if leg.at_berth else 0)) * H))
    wait_h = max(_hours(ready, leg.target), Decimal(0))
    late_h = max(_hours(leg.rta, ready), Decimal(0))
    pd_t = per_day(leg.params, v)
    fuel_sea = _q(sea_h / 24 * pd_t, 1)
    fuel_wait = _q(wait_h / 24 * _d(leg.params["aux_t_per_day"]), 1)
    fuel_t = fuel_sea + fuel_wait
    fuel_sdr = _q(fuel_t * leg.sdr_t, 2)
    return {"option": name, "speed_kn": float(v), "distance_nm": float(distance_nm), "sea_h": _f(sea_h, 1),
            "arrival_utc": iso(ready), "wait_h": _f(wait_h, 1), "late_h": _f(late_h, 1),
            "arrives_by_rta": late_h == 0,
            "speed_allowed": leg.floor - Decimal("0.005") <= v <= leg.cap + Decimal("0.005"),
            "fuel_t_per_day": float(pd_t), "fuel_sea_t": float(fuel_sea), "fuel_wait_t": float(fuel_wait),
            "fuel_t": float(fuel_t), "fuel_sdr": float(fuel_sdr), "suez_dues_sdr": float(dues),
            "total_sdr": float(fuel_sdr + dues)}


def options(status: dict, params: dict, service: dict, rta_row: dict, *, margin_h: Decimal = MARGIN_H,
            suez_ahead: bool = False, dues_sdr: Decimal | None = None, cape: tuple[float | None, list[str]] | None = None
            ) -> dict:
    """{summary: one row, options: rows keyed by option} for an In Transit vessel and one RTA.
    `params` = vessel_params at the vessel's service speed (the cube-law base); `service` its speed row. `cape` =
    `cape_path_nm(status)` when the caller allows the Cape (the graph; never the watch); `dues_sdr` = the Suez dues
    of one transit, counted only when the Cape is compared."""
    planned = _d(service["speed_kn"])
    v_now_f, v_src = eta.sea_speed(status, float(planned))
    v_now = _q(_d(v_now_f), 2)
    cap = max(planned, v_now)
    floor, floor_src = floor_kn(params)
    floor = min(floor, v_now)                        # never asked to sail faster than now to "slow down"
    d_left = _d(status["distance_left_nm"])
    approach = min(_d(eta.APPROACH_NM), d_left)
    approach_h = approach / _d(eta.harbour_kn())
    sea_nm = d_left - approach
    at_berth = rta_row["location"] == "berth"
    rta = ts(rta_row["rta_utc"])
    target = ts(rta - pd.Timedelta(hours=float(margin_h)))
    t0 = ts(status["last_fix"]["ts"])
    sea_target = target - (pd.Timedelta(seconds=float(approach_h * H)) if at_berth else pd.Timedelta(0))
    avail_h = _hours(t0, sea_target)                 # hours for the open-sea part to end on time
    sdr_t = _d(params["price_sdr_per_t"])
    with_cape = cape is not None
    suez_dues = (dues_sdr or Decimal(0)) if (with_cape and suez_ahead) else Decimal(0)
    leg = _Leg(sea_nm, approach_h, t0, target, rta, at_berth, params, sdr_t, floor, cap)
    rows = [_option("keep", v_now, leg, suez_dues, d_left)]
    keep = rows[0]
    if keep["wait_h"] > 0 and sea_nm > 0 and avail_h > 0:
        situation = "early"
        v_jit = sea_nm / avail_h
        if v_jit >= floor:
            rows.append(_option("jit", min(v_jit, v_now), leg, suez_dues, d_left))
        else:
            rows.append(_option("floor", floor, leg, suez_dues, d_left))
            cape_nm, _passages = cape if with_cape else (None, [])
            if with_cape and suez_ahead and cape_nm is not None:
                c_sea = _d(cape_nm) - approach
                v_c = min(max(c_sea / avail_h, floor), cap)
                rows.append(_option("cape", v_c, replace(leg, sea_nm=c_sea), Decimal(0), _d(cape_nm)))
    elif keep["late_h"] > 0:
        situation = "late"
        if sea_nm > 0 and cap > v_now:
            v_need = sea_nm / avail_h if avail_h > 0 else cap
            rows.append(_option("catch_up", min(max(v_need, v_now), cap), leg, suez_dues, d_left))
    else:
        situation = "on_time"
    k_fuel, k_sdr, k_total = _d(keep["fuel_t"]), _d(keep["fuel_sdr"]), _d(keep["total_sdr"])
    for r in rows:
        r |= {"change_fuel_t": float(_d(r["fuel_t"]) - k_fuel), "change_fuel_sdr": float(_d(r["fuel_sdr"]) - k_sdr),
              "change_total_sdr": float(_d(r["total_sdr"]) - k_total)}
    on_time = [r for r in rows if r["arrives_by_rta"] and r["speed_allowed"]]
    pool = on_time or [r for r in rows if r["speed_allowed"]] or rows
    rule = min(pool, key=lambda r: ((0, _d(r["total_sdr"])) if on_time else (_d(r["late_h"]), _d(r["total_sdr"])))
               + (OPTIONS.index(r["option"]),))
    cheapest = min(rows, key=lambda r: (_d(r["total_sdr"]), OPTIONS.index(r["option"])))
    summary = {"vessel_id": status["vessel_id"], "destination": status["destination"], "rta_utc": rta_row["rta_utc"],
               "rta_source": rta_row["rta_source"], "rta_message_id": rta_row.get("message_id"),
               "location": rta_row["location"], "margin_h": float(margin_h), "target_utc": iso(target),
               "situation": situation, "last_fix_utc": iso(t0), "distance_left_nm": float(d_left),
               "sea_part_nm": float(sea_nm), "approach_nm": float(approach), "harbour_kn": eta.harbour_kn(),
               "hours_for_sea_part_h": _f(avail_h, 1), "current_speed_kn": float(v_now), "current_speed_source": v_src,
               "service_speed_kn": float(planned), "floor_speed_kn": float(floor), "floor_source": floor_src,
               "keep_arrival_utc": keep["arrival_utc"], "keep_wait_h": keep["wait_h"], "keep_late_h": keep["late_h"],
               "suez_ahead": suez_ahead, "cape_compared": any(r["option"] == "cape" for r in rows),
               "cheapest_option": cheapest["option"], "rule_option": rule["option"],
               "rule_change_fuel_t": rule["change_fuel_t"], "rule_change_fuel_sdr": rule["change_fuel_sdr"],
               "rule_change_total_sdr": rule["change_total_sdr"]}
    return {"summary": summary, "options": rows}


# "saves {…:change_fuel_t}" reads "saves −160.5 t": a change slot writes its own sign, so after a word of saving or
# reducing it is a double negative (Phase 8's first real run wrote it twice). English + Egyptian Arabic.
SAVING_BEFORE_CHANGE_RE = re.compile(
    r"(?i)(\b(sav(e|es|ed|ing)|reduc\w*|cut(s|ting)?|lower(s|ing)?)\b|يوفر|يوفّر|هيوفر|توفير|يقلل|تقليل)"
    r"[^{}.;:]{0,40}\{[^{}]*:[a-z_]*change_[a-z_]*")


def sign_problems(where: str, text: str) -> list[str]:
    """A change slot right after "save / reduce" (a double negative), for the arrival advisor and the watch brief."""
    return [f"{where}: {m_.group(0)}…: a change_* slot writes its own sign (−160.5 t) — after a word of saving it "
            "reads as a double negative; write \"changes the fuel by {…:change_fuel_t}\" or give both options' own "
            "values (\"{…[jit]:fuel_t} instead of {…[keep]:fuel_t}\")" for m_ in SAVING_BEFORE_CHANGE_RE.finditer(text)]


# "its RTA at 2026-09-18T20:30Z" where 20:30 is the JIT arrival (RTA − margin): an arrival time named as the RTA
RTA_LABEL_RE = re.compile(r"(?i)(\bRTA\b|requested (time|arrival)( of arrival)?|الميعاد المطلوب|ميعاد الوصول المطلوب|"
                          r"ميعاد الرصيف)[^.;{}]{0,30}?(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})Z?")


def rta_label_problems(where: str, text: str, rta_utc: str | None) -> list[str]:
    """A date-time written right after "RTA / requested time / الميعاد المطلوب" must be the RTA itself."""
    if not rta_utc:
        return []
    want = rta_utc.rstrip("Z")
    return [f"{where}: {m_.group(0)} — the requested time of arrival is {rta_utc}; an option's arrival time "
            "(e.g. the jit arrival, RTA − the margin) is never the RTA" for m_ in RTA_LABEL_RE.finditer(text)
            if m_.group(4) != want]


def result(tool: str, rows: list[dict], flt: str) -> dict:
    return ToolResult(tool=tool, status="ok", rows=rows,
                      source=Source(kind="library", name=CODE, filter=flt)).model_dump(mode="json")


def vessel_call(vessel_id: int) -> tuple[str, str] | None:
    """(destination UN/LOCODE, voyage number) of the vessel's current voyage (the voyage file), or None."""
    voy = voyages.voyages()
    if vessel_id not in voy.index:
        return None
    return str(voy.at[vessel_id, "destination_locode"]), str(voy.at[vessel_id, "voyage_no"])

