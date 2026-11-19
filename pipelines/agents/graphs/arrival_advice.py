"""The `arrival_advice` graph: Just-in-Time arrival for one vessel at sea (JIT arrival plan §3; ADR-057's pattern).

"Vessel 21 has a berth at its destination at 14:00 on 15 September: what speed?" Nodes 1–3 are code: every number of
the answer is computed in `tools/arrival.py` from tool results, so it is reproducible and checkable by hand; node 4
(the advisor, one LLM call of the `writer` role) only chooses an option and explains it with number slots; node 5
(the Validator) and node 6 (render) are code.

- **1 inputs:** `voyage_status` at the clock (the vessel must be In Transit), the port (the voyage's destination; a
  question about another port → `not_destination`), `vessel_params` at the service speed, the RTA: the question's,
  else the one known at the clock from `port_call_messages` (D-J1) → `no_rta` when there is none.
- **2 options:** `arrival.options` (keep / jit / floor / catch_up; the Cape only when the delay cannot be absorbed at
  the floor and the canal is ahead, J4: then the remaining route round the Cape from the last fix and the Suez dues
  of one transit, `compute_toll`) + `arrival.summary` with the rule's choice. One option only (on time, or late with
  no faster speed) → a code headline, no model call (`on_time` / `late`).
- **3 context:** the watch's weather rule on the next-leg points (now / +24 / +48 / +72 h, `voyage_watch`'s
  `weather_at` + `weather_alert`) and, with the canal ahead, Suez traffic (PortWatch, `route_advice.traffic`);
  either may be unavailable — the advice goes on.
- **4 advisor / 5 validator:** `ArrivalAdvice` with slots; the Validator: no typed number (dates and times copied
  from the evidence only; vessel names and LOCODEs blanked), every slot bound to a cited numeric field, cited ids
  exist, the recommendation is a computed option and = `rule_option` unless the first reason cites a risk
  (`arrival.weather` with a weather row, or `arrival.traffic` at −20 % or lower); one patch, then
  `validation_failed`.
- **6 render:** `ArrivalAdviceResult`, the assumptions written by code.
Evidence ids `arrival.<name>`; one PostgresSaver thread per question `arrival_advice:<employee>:<as_of date>:<vessel>:<n>`.
"""
# pyright: reportTypedDictNotRequiredAccess=false
import json
import operator
import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from pipelines.agents import skill_loader
from pipelines.agents.deck import slots
from pipelines.agents.deck import validator as v2
from pipelines.agents.graphs import models as m
from pipelines.agents.graphs import route_advice as ra
from pipelines.agents.graphs import voyage_watch as vw
from pipelines.agents.graphs.models import ArrivalRequest
from pipelines.agents.roles import StructuredError
from pipelines.agents.tools import arrival, db, eta, tariff, vessels, voyages
from pipelines.agents.tools.context import RunContext
from pipelines.agents.tools.schemas import ToolResult

MAX_PATCHES = 1
TRAFFIC_DROP_PCT = -20.0                          # the route-cost-advice rule, kept for arrivals (skill arrival-advice)


def _rows(res: dict | None) -> list[dict]:
    return (res or {}).get("rows") or []


# --- 1 inputs -------------------------------------------------------------------------------------------------------

def inputs(user, req: ArrivalRequest, as_of: datetime) -> tuple[dict, str | None]:
    """(evidence, stop status or None)."""
    st = voyages.voyage_status(user, as_of=as_of, vessel_id=req.vessel_id)
    ev = {"arrival.status": st.model_dump(mode="json")}
    if st.status != "ok":
        return ev, st.status
    s = st.rows[0]
    if req.port is not None and req.port != s["destination"]:
        return ev, "not_destination"
    if s["status_at_as_of"] != "In Transit":
        return ev, "not_at_sea"
    p = vessels.vessel_params(user, vessel_id=req.vessel_id)
    ev["arrival.vessel"] = p.model_dump(mode="json")
    if p.status != "ok":
        return ev, p.status
    if req.rta_utc is not None:
        r = arrival.rta_given(req.vessel_id, s["destination"], req.rta_utc, req.location)
    else:
        r = arrival.rta_known(user, req.vessel_id, s["destination"], s["voyage_no"], as_of)
    ev["arrival.rta"] = r.model_dump(mode="json")
    if r.status == "not_permitted":
        return ev, "not_permitted"
    return ev, (None if r.status == "ok" else "no_rta")


# --- 2 options ------------------------------------------------------------------------------------------------------

def compute(user, evidence: dict) -> dict:
    """arrival.options + arrival.summary (+ arrival.toll / arrival.cape_route when the Cape is compared, J4)."""
    s = _rows(evidence["arrival.status"])[0]
    p = _rows(evidence["arrival.vessel"])[0]
    r = _rows(evidence["arrival.rta"])[0]
    ahead = eta.suez_ahead(s["vessel_id"], s["distance_covered_nm"])
    out = arrival.options(s, p, p, r, suez_ahead=ahead)
    ev = {}
    if ahead and any(o["option"] == "floor" for o in out["options"]):
        cape = arrival.cape_path_nm(s)
        toll = tariff.compute_toll(user, vessel_id=s["vessel_id"]).model_dump(mode="json")
        ev["arrival.toll"] = toll
        ev["arrival.cape_route"] = arrival.result("arrival_options", [{
            "option": "cape_route", "distance_nm": cape[0], "passages": cape[1]}] if cape[0] is not None else [],
            "the remaining voyage from the last fix with the Suez Canal closed (searoute, MARNET)")
        dues = Decimal(str(toll["rows"][0]["amount_sdr"])) if toll["status"] == "ok" else None
        out = arrival.options(s, p, p, r, suez_ahead=ahead, dues_sdr=dues, cape=cape)
    ev["arrival.options"] = arrival.result("arrival_options", out["options"],
                                           "per option: sea part / speed, wait at anchor until RTA − margin, fuel by "
                                           "the cube law, SDR at the dated price (tools/arrival.py)")
    ev["arrival.summary"] = arrival.result("arrival_summary", [out["summary"]],
                                           "the RTA, the target, the situation and the rule's choice")
    return ev


# --- 3 context ------------------------------------------------------------------------------------------------------

def context(user, evidence: dict, as_of: datetime) -> dict:
    """arrival.weather (the watch's rule on the next legs) and, with the canal ahead, arrival.traffic."""
    s = _rows(evidence["arrival.status"])[0]
    p = _rows(evidence["arrival.vessel"])[0]
    e = eta.eta_rule(s, p["speed_kn"])
    row = {"vessel_id": s["vessel_id"], "points": eta.next_leg_points(s["vessel_id"], s, e)}
    wx, wsum = vw.weather_at(user, [row])
    flt = f"the watch's rule (waves ≥ {vw.WAVE_MODERATE_M} m or wind ≥ {vw.WIND_MODERATE_KN:g} kn) at now / +24 / " \
          "+48 / +72 h along the route"
    ev = {}
    if wsum["weather_failed_points"] == wsum["weather_points"] and wsum["weather_points"]:
        ev["arrival.weather"] = ToolResult(tool="arrival_risks", status="context_unavailable",
                                           note="Open-Meteo did not answer").model_dump(mode="json")
    else:
        w = vw.weather_alert(row, wx)
        ev["arrival.weather"] = arrival.result("arrival_risks", [{"kind": "weather", **w}] if w else [], flt)
    if _rows(evidence["arrival.summary"])[0]["suez_ahead"]:
        t = ra.traffic(user, as_of.date())
        if "route.traffic" in t:
            ev["arrival.traffic"] = t["route.traffic"]
        else:
            ev["arrival.traffic"] = ToolResult(tool="arrival_risks", status="context_unavailable",
                                               note="IMF PortWatch did not answer").model_dump(mode="json")
    return ev


def deterministic(user, req: ArrivalRequest, as_of: datetime, with_context: bool = True) -> dict:
    """{status, evidence}: nodes 1–3 together (the check calls it directly)."""
    ev, stop = inputs(user, req, as_of)
    if stop:
        return {"status": stop, "evidence": ev}
    ev |= compute(user, ev)
    shape = single_option(ev)
    if with_context and shape is None:
        ev |= context(user, ev, as_of)
    return {"status": shape, "evidence": ev}


def single_option(evidence: dict) -> str | None:
    """`on_time` / `late` when there is only one option (nothing to choose: no model call), else None."""
    if len(_rows(evidence.get("arrival.options"))) > 1:
        return None
    return "on_time" if _rows(evidence["arrival.summary"])[0]["situation"] != "late" else "late"


# --- 4 advisor (one structured call, role writer, skill arrival-advice) ---------------------------------------------

ADVISOR_TASK = """You advise one PortPilot Just-in-Time arrival question with the skill below. Return an ArrivalAdvice (call the
ArrivalAdvice tool): recommendation, headline, reasons, risks. Every number is a slot over the evidence listed; dates
and times are copied from the evidence. Cite in each reason's evidence_ids the ids its slots and claims use.

{skills}"""
PATCH_TASK = """Code checked your ArrivalAdvice and found these problems:
{problems}
Return the whole ArrivalAdvice again with every problem fixed; keep what was right."""
SUMMARY_FIELDS = ("vessel_id", "destination", "rta_utc", "rta_source", "location", "margin_h", "target_utc",
                  "situation", "current_speed_kn", "service_speed_kn", "floor_speed_kn", "floor_source",
                  "keep_arrival_utc", "keep_wait_h", "keep_late_h", "suez_ahead", "cheapest_option", "rule_option",
                  "rule_change_fuel_t", "rule_change_fuel_sdr", "rule_change_total_sdr")


def advisor_digest(evidence: dict) -> str:
    s = _rows(evidence["arrival.summary"])[0]
    st = _rows(evidence["arrival.status"])[0]
    lines = [f"[question] vessel {s['vessel_id']} sailing to {s['destination']} has a requested time of arrival "
             f"{s['rta_utc']} ({s['location']}): what speed?", "[evidence ids you may cite]"]
    for eid in ("arrival.summary", "arrival.options", "arrival.weather", "arrival.traffic", "arrival.rta",
                "arrival.vessel", "arrival.status"):
        res = evidence.get(eid)
        if res is None:
            lines.append(f"- {eid}: not computed")
            continue
        keys = slots.row_keys(res) if len(_rows(res)) > 1 else ()
        lines.append(f"- {eid}: {res['tool']}, status {res['status']}"
                     + (f", rows keyed by {'/'.join(keys)}" if keys else "")
                     + (f" — {res['note']}" if res.get("note") and res["status"] != "ok" else ""))
    lines.append(f"[arrival.summary] {json.dumps({k: s[k] for k in SUMMARY_FIELDS}, ensure_ascii=False)}")
    for r in _rows(evidence["arrival.options"]):
        lines.append(f"[arrival.options] {json.dumps(r, ensure_ascii=False)}")
    for eid in ("arrival.weather", "arrival.traffic"):
        res = evidence.get(eid)
        if res and res["status"] == "ok":
            rows = _rows(res)
            lines.append(f"[{eid}] " + (json.dumps(rows[0], ensure_ascii=False) if rows else "no alert (rows empty)"))
    lines.append(f"[arrival.status] {json.dumps({k: st[k] for k in ('status_at_as_of', 'next_port', 'distance_left_nm', 'recent_sog_kn')}, ensure_ascii=False)}")
    return "\n".join(lines)


def make_advisor(roles):
    def advisor(state: "ArrivalState") -> dict:
        skills = "\n\n".join(skill_loader.load(s) for s in ("arrival-advice", "untrusted-content"))
        msgs = [SystemMessage(ADVISOR_TASK.format(skills=skills)), HumanMessage(advisor_digest(state["evidence"]))]
        if state.get("problems"):
            msgs.append(HumanMessage(PATCH_TASK.format(problems="\n".join(f"- {p}" for p in state["problems"]))
                                     + "\n[your previous ArrivalAdvice]\n" + json.dumps(state["advice"])))
        try:
            reply = roles.get("writer").structured(msgs, m.ArrivalAdvice)
        except StructuredError as exc:
            return {"status": "output_invalid", "problems": [f"advisor: {str(exc)[:300]}"],
                    "llm_usage": [{"node": "advisor", **c} for c in exc.calls]}
        draft, _ = normalize_advice(reply.parsed.model_dump(mode="json"), state["evidence"])
        return {"advice": draft, "patches": state.get("patches", 0) + bool(state.get("problems")),
                "llm_usage": [{"node": "advisor", **c} for c in reply.calls]}
    return advisor


def normalize_advice(advice: dict, evidence: dict) -> tuple[dict, list[str]]:
    """The slot-form fixes of Stage 1 (a unit written twice, a disallowed format, …); numbers are never touched."""
    return ra.normalize_advice(advice, evidence)


# --- 5 validator (code) ---------------------------------------------------------------------------------------------

DATE_TOKEN_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?Z?)?\b")


def _strings(evidence: dict) -> list[str]:
    """Identifiers that may hold digits and are not numbers: the vessel's name, the LOCODEs, the RTA message id."""
    out = set()
    st = _rows(evidence.get("arrival.status"))
    if st:
        out |= {x for x in (st[0].get("destination"), st[0].get("next_port"), st[0].get("origin")) if x}
        out |= {x for x in st[0].get("route") or []}
    rta = _rows(evidence.get("arrival.rta"))
    if rta and rta[0].get("message_id"):
        out.add(rta[0]["message_id"])
    try:
        names = db.fetch("SELECT vessel_name FROM vessels WHERE vessel_id = %s", (st[0]["vessel_id"],)) if st else []
    except Exception:                                  # noqa: BLE001 — a check without a database still validates
        names = []
    out |= {n["vessel_name"] for n in names}
    return sorted(out, key=len, reverse=True)


def _dates(evidence: dict) -> set[str]:
    """The dates / times an advice may copy: the RTA, the target, every option's arrival, the clock's day."""
    s = _rows(evidence.get("arrival.summary"))
    out = set()
    for r in s + _rows(evidence.get("arrival.options")):
        out |= {r[k].rstrip("Z") for k in ("rta_utc", "target_utc", "arrival_utc", "keep_arrival_utc") if r.get(k)}
    w = _rows(evidence.get("arrival.weather"))
    out |= {r["date"] for r in w if r.get("date")}
    out |= {d[:10] for d in out}
    return out


def _justified(evidence: dict, ids: list[str]) -> bool:
    w = evidence.get("arrival.weather")
    if "arrival.weather" in ids and w and w["status"] == "ok" and _rows(w):
        return True
    t = _rows(evidence.get("arrival.traffic"))
    return "arrival.traffic" in ids and bool(t) and t[0]["change_transits_pct"] <= TRAFFIC_DROP_PCT


def _texts(advice: dict) -> list[tuple[str, str, list[str]]]:
    out = [("headline", advice["headline"], sorted({e for r in advice["reasons"] for e in r["evidence_ids"]}))]
    out += [(f"reasons[{i}]", r["text"], r["evidence_ids"]) for i, r in enumerate(advice["reasons"])]
    out += [(f"risks[{i}]", r["text"], r["evidence_ids"]) for i, r in enumerate(advice.get("risks") or [])]
    return out


def validate(advice: dict, evidence: dict) -> list[str]:
    """The problems of an ArrivalAdvice (empty = it passes)."""
    problems = []
    strings, dates = _strings(evidence), _dates(evidence)
    for where, text, ids in _texts(advice):
        missing = [e for e in ids if e not in evidence]
        if missing:
            problems.append(f"{where}: cites unknown evidence {missing}")
        _, bound, errors = slots.render_text(text, evidence)
        problems += [f"{where}: {e}" for e in errors]
        plain = slots.SLOT_RE.sub(" ", text)
        for d in DATE_TOKEN_RE.findall(plain):
            if d.rstrip("Z").replace(" ", "T") not in dates:
                problems.append(f"{where}: date {d} is not a date or time of the evidence (the RTA, the target, an "
                                "option's arrival)")
        typed = v2.number_tokens(plain, strings)
        if typed:
            problems.append(f"{where}: number(s) typed instead of a slot: {[t[0] for t in typed]}")
        uncited = sorted({b.slot.eid for b in bound} - set(ids))
        if uncited and where != "headline":
            problems.append(f"{where}: its slots use {uncited}, not in its evidence_ids")
        problems += arrival.sign_problems(where, text)
        problems += arrival.rta_label_problems(where, text, (_rows(evidence.get("arrival.summary")) or [{}])[0]
                                               .get("rta_utc"))
    names = [r["option"] for r in _rows(evidence.get("arrival.options"))]
    if advice["recommendation"] not in names:
        problems.append(f"recommendation {advice['recommendation']} is not a computed option ({', '.join(names)})")
    rule = _rows(evidence.get("arrival.summary"))[0]["rule_option"]
    if advice["recommendation"] != rule and advice["recommendation"] in names:
        first = advice["reasons"][0]["evidence_ids"] if advice["reasons"] else []
        if not _justified(evidence, first):
            problems.append(f"recommendation {advice['recommendation']} is not the rule's option ({rule}: the "
                            "cheapest at the berth by the RTA) and the first reason cites no risk that justifies it "
                            "(arrival.weather with a weather row, or arrival.traffic at −20 % or lower)")
    return problems


# --- 6 render (code) ------------------------------------------------------------------------------------------------

def assumptions(evidence: dict) -> list[str]:
    s = _rows(evidence["arrival.summary"])[0]
    v = _rows(evidence["arrival.vessel"])[0]
    src = ("given in the question" if s["rta_source"] == "question"
           else f"the latest port-call message known at the clock ({s['rta_message_id']})")
    out = [f"RTA {s['rta_utc']} at the {s['location'].replace('_', ' ')}, {src}; target = RTA − {s['margin_h']:g} h "
           f"({s['target_utc']}).",
           f"Current sea speed {s['current_speed_kn']} kn ({s['current_speed_source']}), constant to the end of the "
           f"sea part; the last {s['approach_nm']:g} nm at {s['harbour_kn']} kn (the harbour approach, the same in "
           "every option and not priced).",
           f"Lowest speed allowed {s['floor_speed_kn']} kn: {s['floor_source']}; highest: the service speed "
           f"{s['service_speed_kn']} kn.",
           f"Fuel per sea day = main engine × (speed / {v['ref_speed_kn']} kn)³ + auxiliaries; waiting at anchor burns "
           f"the auxiliaries only ({v['aux_t_per_day']} t per day); IMO 2018 yearly averages for {v['imo_ship_type']} "
           f"{v['imo_size_bin']}; the cube law is an approximation at low speeds.",
           f"{v['fuel']} {v['price_usd_per_t']} USD/t of {v['price_date']} at {v['usd_per_sdr']} USD per SDR of "
           f"{v['rate_date']} = {v['price_sdr_per_t']} SDR/t.",
           "Port dues, anchorage fees, charter-party terms (who pays for waiting or slow steaming) and emissions are not "
           "modelled; intermediate ports are passed without a stop (synthetic voyages)."]
    if s["cape_compared"]:
        out.append("The Cape option: the remaining voyage from the last position with the Suez Canal closed (searoute); "
                   "the Suez options carry the dues of one transit in the vessel's condition.")
    for eid, what in (("arrival.weather", "Weather"), ("arrival.traffic", "Suez traffic")):
        res = evidence.get(eid)
        if res is not None and res["status"] != "ok":
            out.append(f"{what} context unavailable ({res.get('note') or res['status']}).")
    return out


def shape_headline(status: str, evidence: dict) -> str:
    s = _rows(evidence["arrival.summary"])[0]
    keep = _rows(evidence["arrival.options"])[0]
    if status == "on_time":
        return (f"At its current speed the vessel reaches the {s['location'].replace('_', ' ')} at "
                f"{keep['arrival_utc']}, within {s['margin_h']:g} h of the requested time {s['rta_utc']}: keep the "
                "speed, there is nothing to change.")
    return (f"The vessel cannot make the requested time {s['rta_utc']}: at its current speed it arrives "
            f"{keep['late_h']} h late ({keep['arrival_utc']}) and no faster speed is available; tell the port.")


def sources(evidence: dict) -> list[dict]:
    return [{"evidence": eid, "tool": res["tool"], "status": res["status"], **(res.get("source") or {})}
            for eid, res in sorted(evidence.items())]


STOP_NOTES = {"not_destination": "the question's port is not the vessel's destination on this voyage (intermediate "
                                 "ports are passed without a stop in this data)",
              "not_at_sea": "the vessel is not at sea at the clock: no arrival to plan",
              "no_rta": "no RTA: none given in the question and none known at the clock from the port's messages"}


# --- the graph ------------------------------------------------------------------------------------------------------

class ArrivalState(TypedDict, total=False):
    request: dict
    status: str | None
    evidence: dict
    advice: dict
    problems: list[str]
    patches: int
    llm_usage: Annotated[list[dict], operator.add]
    result: dict


def _req(state) -> ArrivalRequest:
    return ArrivalRequest.model_validate(state["request"])


def node_inputs(state: ArrivalState, runtime: Runtime[RunContext]) -> dict:
    ev, stop = inputs(runtime.context.user, _req(state), runtime.context.as_of)
    return {"evidence": ev, "status": stop}


def node_options(state: ArrivalState, runtime: Runtime[RunContext]) -> dict:
    ev = {**state["evidence"], **compute(runtime.context.user, state["evidence"])}
    return {"evidence": ev, "status": single_option(ev)}


def node_context(state: ArrivalState, runtime: Runtime[RunContext]) -> dict:
    return {"evidence": {**state["evidence"], **context(runtime.context.user, state["evidence"],
                                                        runtime.context.as_of)}}


def node_validator(state: ArrivalState) -> dict:
    problems = validate(state["advice"], state["evidence"])
    if problems and state.get("patches", 0) >= MAX_PATCHES:
        return {"problems": problems, "status": "validation_failed"}
    return {"problems": problems}


def _base(state, runtime) -> dict:
    ev = state.get("evidence") or {}
    return {"status": state.get("status") or "ok", "request": state["request"],
            "as_of": runtime.context.as_of.isoformat(), "summary": (_rows(ev.get("arrival.summary")) or [{}])[0],
            "options": _rows(ev.get("arrival.options")), "sources": sources(ev), "problems": state.get("problems") or []}


def node_render(state: ArrivalState, runtime: Runtime[RunContext]) -> dict:
    ev, status = state["evidence"], state.get("status")
    out = _base(state, runtime)
    if status in ("on_time", "late"):
        out |= {"recommendation": "keep", "headline": shape_headline(status, ev), "assumptions": assumptions(ev)}
    elif status is None and state.get("advice"):
        a = state["advice"]
        fill = lambda t: slots.render_text(t, ev)[0]          # noqa: E731
        out |= {"recommendation": a["recommendation"], "headline": fill(a["headline"]),
                "reasons": [fill(r["text"]) for r in a["reasons"]], "risks": [fill(r["text"]) for r in a["risks"]],
                "assumptions": assumptions(ev)}
    return {"result": m.ArrivalAdviceResult.model_validate(out).model_dump(mode="json"), "status": out["status"]}


def node_failed(state: ArrivalState, runtime: Runtime[RunContext]) -> dict:
    out = _base(state, runtime)
    note = STOP_NOTES.get(out["status"])
    if note:
        out["problems"] = out["problems"] + [note]
    if out["status"] in ("output_invalid", "validation_failed") and out["summary"]:
        out["assumptions"] = assumptions(state["evidence"])
    return {"result": m.ArrivalAdviceResult.model_validate(out).model_dump(mode="json")}


def _after_inputs(state):
    return "failed" if state.get("status") else "options"


def _after_options(state):
    return "render" if state.get("status") in ("on_time", "late") else "context"


def _after_advisor(state):
    return "failed" if state.get("status") == "output_invalid" else "validator"


def _after_validator(state):
    if state.get("status") == "validation_failed":
        return "failed"
    return "advisor" if state.get("problems") else "render"


def build_graph(roles, checkpointer=None):
    """The compiled arrival advice graph; `roles` = `roles.Roles()` (real models) or `roles.FakeRoles(script)`.
    Invoke with {"request": ArrivalRequest dump}, `context=RunContext(user, as_of=…)` and a thread id."""
    g = StateGraph(ArrivalState, context_schema=RunContext)
    for name, fn in (("inputs", node_inputs), ("options", node_options), ("context", node_context),
                     ("advisor", make_advisor(roles)), ("validator", node_validator), ("render", node_render),
                     ("failed", node_failed)):
        g.add_node(name, fn)
    g.add_edge(START, "inputs")
    g.add_conditional_edges("inputs", _after_inputs, ["options", "failed"])
    g.add_conditional_edges("options", _after_options, ["context", "render"])
    g.add_edge("context", "advisor")
    g.add_conditional_edges("advisor", _after_advisor, ["validator", "failed"])
    g.add_conditional_edges("validator", _after_validator, ["advisor", "render", "failed"])
    g.add_edge("render", END)
    g.add_edge("failed", END)
    return g.compile(checkpointer=checkpointer)


THREAD_PREFIX = "arrival_advice:"


def thread_prefix(employee_id: int, as_of: datetime, vessel_id: int) -> str:
    return f"{THREAD_PREFIX}{employee_id}:{as_of.date().isoformat()}:{vessel_id}:"


def new_thread_id(pool, employee_id: int, as_of: datetime, vessel_id: int) -> str:
    """`arrival_advice:<employee>:<as_of date>:<vessel>:<n>`, n = the next free number."""
    prefix = thread_prefix(employee_id, as_of, vessel_id)
    with pool.connection() as conn:
        rows = conn.execute("SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id LIKE %s",
                            (prefix.replace("_", r"\_") + "%",)).fetchall()
    used = [int(x.group(1)) for r in rows if (x := re.fullmatch(re.escape(prefix) + r"(\d+)", r["thread_id"]))]
    return f"{prefix}{max(used, default=0) + 1}"


def thread_owner(thread_id: str) -> int | None:
    head = thread_id.removeprefix(THREAD_PREFIX).split(":", 1)[0]
    return int(head) if thread_id.startswith(THREAD_PREFIX) and head.isdigit() else None


def result_summary(st: dict) -> dict:
    """What a caller may see of a final state (the CLI `Arrival_advice.py` and the API, Arrival advice web plan P1)."""
    r = st.get("result") or {}
    usage = st.get("llm_usage") or []
    return {"status": r.get("status"), "recommendation": r.get("recommendation"), "headline": r.get("headline"),
            "numbers": _numbers(st, r),
            "summary": {k: (r.get("summary") or {}).get(k) for k in SUMMARY_FIELDS},
            "options": [{k: o.get(k) for k in ("option", "speed_kn", "arrival_utc", "wait_h", "late_h", "fuel_t",
                                               "fuel_sdr", "total_sdr", "change_fuel_t", "change_total_sdr")}
                        for o in r.get("options") or []],
            "reasons": r.get("reasons"), "risks": r.get("risks"), "assumptions": r.get("assumptions"),
            "problems": r.get("problems"),
            "sources": [f"{s['evidence']}: {s['tool']} {s['status']} — {s.get('name')} ({s.get('filter')})"
                        for s in r.get("sources") or []],
            "model_calls": len(usage), "cached": sum(bool(c.get("cached")) for c in usage)}


def _numbers(st: dict, r: dict) -> dict:
    """D-FE-1 (as `route_advice._numbers`): the number spans of the advisor's headline, reasons and risks, rendered
    again from the advice and the evidence. A code headline (`on_time` / `late`) or a stopped advice has none."""
    a, ev = st.get("advice") or {}, st.get("evidence") or {}
    if not a or not r.get("reasons"):
        return {"headline": [], "reasons": [], "risks": []}
    return {"headline": slots.number_spans(a.get("headline") or "", ev, r.get("headline")),
            "reasons": [slots.number_spans(t.get("text") or "", ev, got)
                        for t, got in zip(a.get("reasons") or [], r.get("reasons") or [])],
            "risks": [slots.number_spans(t.get("text") or "", ev, got)
                      for t, got in zip(a.get("risks") or [], r.get("risks") or [])]}

