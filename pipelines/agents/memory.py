"""Conversation memory (FastAPI plan §6a, owner A3 "intelligent memory"; ADR-065): a follow-up such as "and week
24?", "when will it arrive?", "وسفنه فين دلوقتي؟" becomes a standalone question before the router sees it — so the
router, RBAC per question, the slots and the checks run exactly as for a first question.

What is remembered per turn (`frame_of`): the entities of the user's own words and of the answer's **cited** rows
(the rows its slots bound; else the rows of the evidence it cited) — vessel ids, report weeks, customer ids, the route,
the uploaded document — never a number of an answer (`mask` replaces every slot), never text of a document, an upload
or the web, and nothing of a refused part (a refused tool never ran, so it left no rows).

How a follow-up is understood (`resolve`), code first:
1. not a follow-up (no lead-in "and / what about / و / طب", no pronoun or deictic, no relative time) → as asked;
2. an ellipsis ("And week 24?", "والأسبوع اللي بعده؟", "And at 14 knots?") → the previous standalone question with that
   value swapped in (or added);
3. a pronoun / lead-in ("When will it arrive?", "Was that above budget?", "وسفنه فين؟") → the follow-up + the carried
   entities in words; one value per kind, or `the first one`, or `the two` → the last two; a singular reference to
   several values, `the other one` with one, or nothing to carry → **clarify** (the API asks back, no tool runs);
4. only when the rules find no reading: one small `tools` call (`StandaloneQuestion`), accepted only if every entity it
   names is in the frame or the follow-up and it adds no number of its own — else clarify.
"""
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

KINDS = ("vessel", "report_week", "customer", "route", "document", "speed_kn")
HISTORY = 5
ROW_FIELDS = {"vessel": "vessel_id", "report_week": "report_week", "customer": "customer_id", "document": "document_id"}

LEAD = re.compile(r"^\s*(and|also|what about|how about|and what about|so|then)\b[\s,]*|^\s*(طب\s*)?و(?=\S)|^\s*طب\s+",
                  re.I)
PRONOUN_EN = re.compile(r"\b(it|its|it's|that|this|those|them|they|their|there|the same|the first one|the second one|"
                        r"the last one|the other one|the other|the two|both|that customer|that vessel|that figure)\b",
                        re.I)
PRONOUN_AR = re.compile(r"(ده|دي|دول|بتاعه|بتاعها|بتاعهم|نفسه|نفسها|الاتنين|التانية|التاني|الأولى|الاولى|اللي فاتت)")
PLURAL = re.compile(r"\b(the two|both|them|they|their|those)\b|الاتنين|هما|بتوعهم|دول", re.I)
FIRST = re.compile(r"\bthe first( one)?\b|الأولى|الاولى|أول واحدة", re.I)
OTHER = re.compile(r"\bthe other( one)?\b|التانية|التاني|التانيه", re.I)
NEXT_WEEK = re.compile(r"\b(the )?(week after|next week|following week)\b|اللي بعده|الجاي", re.I)
PREV_WEEK = re.compile(r"\b(the )?(week before|previous week|prior week)\b|اللي قبله|اللي فات", re.I)
COMPARE = re.compile(r"\bcompar\w*\b|\bversus\b|\bvs\.?\b|قارن", re.I)

WEEK = re.compile(r"\bweeks? (\d{1,2})\b|الأسبوع (\d{1,2})|الاسبوع (\d{1,2})", re.I)
VESSEL = re.compile(r"\bvessels? (\d{1,3})(?: and (\d{1,3}))?\b|\b[A-Z][a-z]+ Voyager (\d{3})\b|"
                    r"السفين[ةه] (\d{1,3})|السفن (\d{1,3}) ?و ?(\d{1,3})")
CUSTOMER = re.compile(r"\bcustomer (\d{1,3})\b|العميل (\d{1,3})")
SPEED = re.compile(r"\b(\d{1,2}(?:\.\d)?) knots?\b|(\d{1,2}(?:\.\d)?) عقدة")
SLOT = re.compile(r"\{[^{}]+\}")
ROUTE_FILTER = re.compile(r"\b([A-Z]{2}[A-Z2-9]{3}) → ([A-Z]{2}[A-Z2-9]{3})(?:, vessel_id = (\d+))?")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _ints(m: re.Match) -> list[int]:
    return [int(g) for g in m.groups() if g]


def own_entities(text: str) -> dict[str, list]:
    """The entities the user's own words name (values only, in order)."""
    out: dict[str, list] = {}
    for kind, rx in (("report_week", WEEK), ("vessel", VESSEL), ("customer", CUSTOMER)):
        vals = [v for m in rx.finditer(text) for v in _ints(m)]
        if vals:
            out[kind] = list(dict.fromkeys(vals))
    speeds = [float(g) for m in SPEED.finditer(text) for g in m.groups() if g]
    if speeds:
        out["speed_kn"] = [int(s) if s.is_integer() else s for s in speeds]
    return out


def is_follow_up(text: str) -> bool:
    return bool(LEAD.search(text) or PRONOUN_EN.search(text) or PRONOUN_AR.search(text) or NEXT_WEEK.search(text)
                or PREV_WEEK.search(text))


def _add(frame: dict[str, list], kind: str, value) -> None:
    if value is not None and value not in frame.setdefault(kind, []):
        frame[kind].append(value)


def frame_of(state: dict, standalone: str) -> dict[str, list]:
    """The turn's entity frame: the standalone question's own entities + the answer's cited rows."""
    frame: dict[str, list] = {k: list(v) for k, v in own_entities(standalone).items()}
    evidence = state.get("evidence") or {}
    rows = [(b.get("eid"), b.get("row")) for b in state.get("bound") or []]
    picked = [evidence[e]["rows"][r] for e, r in rows if e in evidence and isinstance(r, int)
              and r < len(evidence[e].get("rows") or [])]
    if not picked:                                    # no number bound: the rows of the evidence the answer cited
        cited = (state.get("answer") or {}).get("evidence_ids") or []
        picked = [row for e in cited for row in (evidence.get(e) or {}).get("rows") or []]
    for row in picked:
        for kind, fld in ROW_FIELDS.items():
            if kind == "document" and row.get("lane") != "upload":
                continue                              # only the asker's own upload is a "document" to come back to
            _add(frame, kind, row.get(fld))
    for res in evidence.values():                     # the route of a route advice, the upload of a search
        if res.get("tool") == "route_advice":         # the route is in the source's filter, "SGSIN → NLRTM, …"
            m = ROUTE_FILTER.search(str((res.get("source") or {}).get("filter") or ""))
            if m:
                _add(frame, "route", f"{m[1]}-{m[2]}")
                if m[3]:
                    _add(frame, "vessel", int(m[3]))
        if res.get("tool") == "search_documents" and "document" not in frame:
            for row in res.get("rows") or []:
                if row.get("lane") == "upload":
                    _add(frame, "document", row.get("document_id"))
    return {k: v for k, v in frame.items() if v}


def mask(answer_text: str | None) -> str | None:
    """The stored answer: every slot replaced by ⟨n⟩, so no later turn can copy a figure (§6a.1)."""
    return SLOT.sub("⟨n⟩", answer_text) if answer_text else answer_text


@dataclass
class Turn:
    question: str
    standalone: str
    frame: dict[str, list]


@dataclass
class Resolution:
    standalone: str
    by: str                                           # none | code | model | clarify
    used: dict[str, list] = field(default_factory=dict)
    clarify: str | None = None
    options: list = field(default_factory=list)


class StandaloneQuestion(BaseModel):
    text: str = Field(description="the follow-up rewritten as one complete question, in the user's language")
    needs_clarification: bool = Field(default=False, description="true when the context does not say what is meant")


def _words(kind: str, value, lang: str) -> str:
    en = {"vessel": "vessel {v}", "report_week": "week {v} of 2025", "customer": "customer {v}",
          "route": "the route {v}", "document": "my uploaded document {v}", "speed_kn": "{v} knots"}
    ar = {"vessel": "السفينة {v}", "report_week": "الأسبوع {v} من 2025", "customer": "العميل {v}",
          "route": "المسار {v}", "document": "المستند اللي رفعته {v}", "speed_kn": "{v} عقدة"}
    return (ar if lang == "ar" else en)[kind].format(v=value)


def _clarify(kind: str, options: list, lang: str) -> Resolution:
    name = {"vessel": ("vessel", "سفينة"), "customer": ("customer", "عميل"), "report_week": ("week", "أسبوع"),
            "document": ("document", "مستند"), "route": ("route", "مسار"), "speed_kn": ("speed", "سرعة")}[kind]
    if options:
        text = (f"تقصد أنهي {name[1]}: {' ولا '.join(map(str, options))}؟" if lang == "ar"
                else f"Which {name[0]} do you mean: {' or '.join(map(str, options))}?")
    else:
        text = (f"تقصد أنهي {name[1]}؟ اكتبه في السؤال." if lang == "ar"
                else f"Which {name[0]} do you mean? Please name it in the question.")
    return Resolution("", "clarify", {}, text, options)


def _swap(prev: str, kind: str, old, new) -> str | None:
    rx = {"report_week": (r"(week |الأسبوع |الاسبوع )" + str(old) + r"\b"),
          "vessel": (r"(vessel |السفينة |السفينه )" + str(old) + r"\b")}.get(kind)
    if rx and re.search(rx, prev):
        return re.sub(rx, lambda m: m.group(1) + str(new), prev, count=1)
    return None


def resolve(question: str, lang: str, history: list[Turn], rewrite=None) -> Resolution:
    """The follow-up as a standalone question (§6a.2). `rewrite(question, history) -> StandaloneQuestion | None` is
    the one model call; None = rules only."""
    own = own_entities(question)
    if not is_follow_up(question):
        return Resolution(question, "none", own)
    if not history:                                   # a follow-up with nothing before it (or after a refused
        if own:                                       # question, which leaves no history): its own words decide
            return Resolution(question, "none", own)
        return _clarify(_wanted_kind(question), [], lang)
    prev = history[-1]
    pf = prev.frame
    body = LEAD.sub("", question).strip()
    # 2. ellipsis: the follow-up is only a new value (or a relative week) → the previous question with it
    if pf.get("report_week") and (NEXT_WEEK.search(question) or PREV_WEEK.search(question)):
        if len(pf["report_week"]) != 1:
            return _clarify("report_week", pf["report_week"], lang)
        new = pf["report_week"][0] + (1 if NEXT_WEEK.search(question) else -1)
        swapped = _swap(prev.standalone, "report_week", pf["report_week"][0], new)
        if swapped:
            return Resolution(swapped, "code", {**pf, "report_week": [new]})
    stripped = re.sub(r"[?؟.!\s]", "", WEEK.sub("", VESSEL.sub("", SPEED.sub("", body))))
    if own and len(stripped) <= 6 and not COMPARE.search(question):
        out, used = prev.standalone, {**pf}
        for kind, vals in own.items():
            old = (pf.get(kind) or [None])[0]
            swapped = _swap(out, kind, old, vals[0]) if old is not None else None
            if swapped:
                out = swapped
            elif kind == "speed_kn" and lang == "en":   # "… via Suez or the Cape at 14 knots?"
                out = re.sub(r"\s*\?\s*$", "", out) + f" at {_words(kind, vals[0], 'en')}?"
            else:
                out = out.rstrip("?؟ ") + f" ({_words(kind, vals[0], lang)})" + ("؟" if lang == "ar" else "?")
            used[kind] = vals
        return Resolution(out, "code", used)
    # 3. pronoun / lead-in: carry what the follow-up does not say itself
    carried: dict[str, list] = {}
    merged: dict[str, list] = {}
    for t in history[-HISTORY:]:                      # the last values per kind, newest last
        for k, v in t.frame.items():
            merged[k] = [x for x in merged.get(k, []) if x not in v] + list(v)
    for kind in KINDS:
        if kind in own and not COMPARE.search(question):
            continue
        vals = pf.get(kind) or []
        if PLURAL.search(question) and kind == "vessel" and len(merged.get(kind, [])) >= 2:
            carried[kind] = merged[kind][-2:]
        elif OTHER.search(question) and kind == "vessel":
            if len(vals) == 2:
                carried[kind] = [vals[1]]
            else:
                return _clarify(kind, [], lang)
        elif not vals:
            continue
        elif len(vals) == 1:
            carried[kind] = vals
        elif FIRST.search(question):
            carried[kind] = vals[:1]
        elif kind in ("vessel", "customer") and not PLURAL.search(question):
            return _clarify(kind, vals, lang)
        elif kind in ("vessel", "customer"):
            carried[kind] = vals
        else:
            carried[kind] = vals[-1:]
    if COMPARE.search(question) and "report_week" in own and pf.get("report_week"):
        carried["report_week"] = list(dict.fromkeys(pf["report_week"] + own["report_week"]))
    if not carried and not own:
        if rewrite is not None and any(pf.values()):
            return _model(question, lang, history, rewrite)
        return _clarify(_wanted_kind(question), [], lang)
    compare = bool(COMPARE.search(question))
    words = ", ".join(_words(k, v, lang) for k, vs in carried.items() for v in vs if k not in own or compare)
    standalone = f"{question.rstrip()} ({words})" if words else question
    return Resolution(standalone, "code", {**own, **carried})


def _wanted_kind(question: str) -> str:
    if re.search(r"\bcustomer|عميل|العميل", question, re.I):
        return "customer"
    if re.search(r"\bweek|الأسبوع|الاسبوع", question, re.I):
        return "report_week"
    if re.search(r"\bdocument|file|المستند|الملف", question, re.I):
        return "document"
    return "vessel"


REWRITE_TASK = ("Rewrite the user's last message as one complete question in the same language, using only the earlier "
                 "questions and the entities listed. Do not answer it. Do not add any number, vessel, week or customer "
                 "that is not listed or written by the user. If it is unclear what the user means, set "
                 "needs_clarification to true.")


def model_rewrite(roles):
    """The one guarded call of step 4: the `tools` role (flash-lite), a prompt of a few hundred tokens — the earlier
    standalone questions and their entity frames, never an answer (they are masked anyway) nor any document text."""
    from langchain_core.messages import HumanMessage, SystemMessage

    def rewrite(question: str, history: list[Turn]) -> StandaloneQuestion | None:
        lines = [f"{i}. {t.standalone}  — entities: {t.frame}" for i, t in enumerate(history[-HISTORY:], 1)]
        msgs = [SystemMessage(REWRITE_TASK),
                HumanMessage("Earlier questions:\n" + "\n".join(lines) + f"\n\nThe user's last message: {question}")]
        try:
            out = roles.get("tools").structured(msgs, StandaloneQuestion).parsed
        except Exception:  # noqa: BLE001 — an invalid or missing reply means "ask back", never a guess
            return None
        return out if isinstance(out, StandaloneQuestion) else None
    return rewrite


def _model(question: str, lang: str, history: list[Turn], rewrite) -> Resolution:
    allowed: dict[str, set] = {}
    for t in history[-HISTORY:]:
        for k, v in t.frame.items():
            allowed.setdefault(k, set()).update(map(str, v))
    out = rewrite(question, history)
    if out is None or out.needs_clarification:
        return _clarify(_wanted_kind(question), [], lang)
    named = own_entities(out.text)
    invented = [(k, v) for k, vs in named.items() for v in vs
                if str(v) not in allowed.get(k, set()) and str(v) not in question]
    known = {str(v) for vs in allowed.values() for v in vs} | set(NUMBER.findall(question)) | {"2025"}
    added_numbers = [n for n in NUMBER.findall(out.text) if n not in known]
    if invented or added_numbers:
        return _clarify(_wanted_kind(question), [], lang)
    return Resolution(out.text, "model", named)
