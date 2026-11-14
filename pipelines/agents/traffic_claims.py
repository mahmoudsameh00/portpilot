"""Shared M17 claim policy for decks, analysis notes and Q&A (stabilization R5/R6).

M17 measures invoice counts against Suez transits, never revenue or a news effect. Tool/source provenance and
citations select the evidence; a chat's generated evidence ID has no special meaning. Classification is deliberately
conservative: unfamiliar joint claims must use the fixed wording or separate the two facts. This is a bounded
language guard, not a general natural-language proof or a causal inference engine.
"""
import re
import unicodedata
from typing import Literal

from pipelines.agents.deck import slots

Kind = Literal["causal", "association", "negative", "insufficient", "neutral", "uncertain"]
VIEWS = frozenset(f"{s}.kpi_traffic_link" for s in ("finance", "finance_test", "finance_scenario"))


def normal(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower().translate(str.maketrans("أإآى٠١٢٣٤٥٦٧٨٩", "اااي0123456789"))
    return " ".join(re.sub(r"[\u064b-\u065f\u0670\u0640]", "", text).split())


def pattern(text: str) -> re.Pattern:
    return re.compile(text, re.I)


TRAFFIC = pattern(r"\b(?:suez|transits?|canal|traffic|red sea|houthis?|news)\b|السويس|العبور|عبور السفن|حرك[ةه] السفن|البحر الاحمر|الحوثي|الاخبار")
FINANCE = pattern(r"\b(?:billing|billed|bills|revenues?|invoices?|income|turnover|profits?|margins?)\b|فواتير|فوتر|ايراد|دخل|ارباح")
MONEY = pattern(r"\b(?:revenues?|income|turnover|profits?|margins?|invoice (?:values?|amounts?)|billing (?:values?|amounts?))\b|ايراد|ارباح|قيم[ةه] الفواتير|مبلغ الفواتير")
NEWS = pattern(r"\b(?:news|houthis?|red sea|attacks?|crisis)\b|اخبار|الحوثي|البحر الاحمر|هجمات|ازم[ةه]")
CAUSE = pattern(r"\b(?:because|due to|driven by|caus\w*|owing to|as a result|led to|leads? to|result(?:s|ed)? (?:from|in)"
                r"|reflect(?:s|ed|ing)?|thanks to|hit by|explain(?:s|ed)?|on the back of|underpin\w*|boost\w*|fuel\w*)\b"
                r"|بسبب|نتيج[ةه]|ادي الي|ادت الي|يسبب|سبب[ته]?|يفسر|بتفسر|اثر|تاثير")
ASSOCIATION = pattern(r"\b(?:mov(?:e|es|ed|ing) (?:with|in line with)|in line with|in step with|track(?:s|ed|ing)?"
                      r"|follow(?:s|ed|ing)?|correlat\w*|link(?:s|ed)?|associat\w*|mirror\w*|went with|go(?:es)? with)\b"
                      r"|ارتباط|مرتبط|تتماشي|تتحرك مع|بيتحرك مع|بتتحرك مع|تواكب|بتواكب|علاق[ةه]")
# Qualifiers allowed between "no" and "link": a fixed list, so "no doubt the link …" is never read as a denial.
_QUAL = (r"(?:(?:measurable|measured|significant|observed|statistical|statistically significant|clear|detectable"
         r"|meaningful|suez|billing|traffic|invoice[- ]count) ){0,3}")
NEGATIVE = pattern(r"\b(?:no " + _QUAL + r"(?:correlation|link|association)|not (?:correlated|linked|associated)"
                   r"|(?:does|do|did) not (?:correlate|move|track)"
                   r"|(?:(?:does|do|did) not show|(?:has|have) not shown) (?:a |any )?" + _QUAL
                   + r"(?:correlation|link|association)"
                   r"|(?:is|are|was|were) not claimed to (?:move|track|correlate)"
                   r"|cannot be said to (?:have )?(?:moved?|track(?:ed)?|correlated?))\b"
                   r"|(?:لا يوجد|مفيش|مافيش|ليس هناك|لم نجد|لم يظهر) (?:اي )?(?:ارتباط|علاق[ةه])|غير مرتبط|مش مرتبط")
INSUFFICIENT = pattern(r"\b(?:too few weeks|insufficient (?:weeks|data)|not enough (?:weeks|data)"
                       r"|not (?:yet )?measurable|cannot (?:yet )?be measured|link (?:is|=) ?null)\b"
                       r"|اسابيع (?:غير كافي[ةه]|قليل[ةه])|البيانات (?:غير كافي[ةه]|مش كفاي[ةه])|لسه بدري")
CHANGE = pattern(r"\b(?:fell|drop\w*|declin\w*|rose|ris\w*|grew|increas\w*|decreas\w*)\b|قلت|قل|زاد|زادت|انخفض|انخفضت|ارتفع|ارتفعت|نزل")
BRIDGE = pattern(r"\b(?:as|while|with|alongside)\b|مع|لما|بالتزامن")
# Only explicit epistemic disclaimers are exempt. A remote 'not' must never negate an entire paragraph.
DISCLAIMER = pattern(r"^(?:we cannot infer|we cannot conclude|there is no evidence that|it is not established that)\b.*$"
                      r"|^(?:لا يمكن استنتاج|لا يمكن اثبات|لا يوجد دليل علي ان|مفيش دليل ان).*$")
NEGATED_CAUSE = pattern(r"\b(?:(?:does|do|did|can) not|cannot|never) (?:establish|prove|imply|mean)\b|لا يثبت|لا تثبت|لا يعني|مش معناه")
GENERAL_CORRELATION = pattern(r"^(?:the )?(?:correlation|association) between\b|^(?:ان )?الارتباط بين")
REFERENT = pattern(r"\b(?:this|that|it|therefore|hence|thus)\b|هذا|ذلك|ده|دا|وده|وبالتالي|ولذلك")
SENTENCES = re.compile(r"(?<!\d)[.!?؟;؛\n]+|[.!?؟;؛\n]+(?!\d)")
WEEK = pattern(r"\bweek\s+(\d+)\b|(?:الاسبوع|اسبوع)\s+(\d+)")
# "null before week 13", "from week 13": the rule's threshold, not the week the claim is about
THRESHOLD_WEEK = pattern(r"\b(?:before|until|from|after|since)\s+week\s+\d+\b"
                         r"|(?:قبل|حتي|بعد|منذ)\s+(?:الاسبوع|اسبوع)\s+\d+")
UNITS = re.compile(r"[()]|(?<=[.!?؟;؛])\s+|\n+")   # sentence / `;` ends, and the brackets `_units` keeps whole

WORDS = {
    "link": {
        "en": "The weekly invoice count is associated with Suez transits over the observed weeks. This does not establish causation.",
        "ar": "يوجد ارتباط مقاس بين عدد الفواتير الاسبوعي وعبور السفن بقناة السويس خلال الاسابيع المرصودة. هذا لا يثبت السببية.",
    },
    "no_link": {
        "en": "No measurable link was found between the weekly invoice count and Suez transits over the observed weeks.",
        "ar": "لا يوجد ارتباط مقاس بين عدد الفواتير الاسبوعي وعبور السفن بقناة السويس خلال الاسابيع المرصودة.",
    },
    None: {
        "en": "There are too few weeks to measure a link between the weekly invoice count and Suez transits.",
        "ar": "الاسابيع غير كافية لقياس ارتباط بين عدد الفواتير الاسبوعي وعبور السفن بقناة السويس.",
    },
}


def wording(verdict: str | None, lang: str = "en") -> str:
    return WORDS[verdict if verdict in ("link", "no_link") else None]["ar" if lang == "ar" else "en"]


def classify(sentence: str) -> Kind:
    if not (TRAFFIC.search(sentence) and FINANCE.search(sentence)):
        return "neutral"
    # Split contrast clauses first in problems(): a disclaimer cannot excuse 'but traffic caused billing ...'.
    if DISCLAIMER.fullmatch(sentence):
        # One denied proposition only; an added positive assertion needs its own check.
        return "neutral" if len(CAUSE.findall(sentence)) + len(ASSOCIATION.findall(sentence)) <= 1 else "uncertain"
    disclaimer = NEGATED_CAUSE.search(sentence)
    if disclaimer:
        before = sentence[:disclaimer.start()]
        if CAUSE.search(before):
            return "causal"
        if NEGATIVE.search(before):
            return "negative"
        if ASSOCIATION.search(before) and not GENERAL_CORRELATION.search(sentence):
            return "association"
        return "neutral"
    if CAUSE.search(sentence):
        return "causal"
    if INSUFFICIENT.search(sentence):
        return "insufficient"
    if NEGATIVE.search(sentence):
        return "negative"
    if ASSOCIATION.search(sentence):
        return "association"
    if BRIDGE.search(sentence) and len(CHANGE.findall(sentence)) >= 2:
        return "uncertain"
    # Two independently stated quantities are neutral; a change connector was handled above.
    if len(re.findall(r"\bvalue\b|\d+(?:\.\d+)?", sentence)) >= 2 and not CHANGE.search(sentence):
        return "neutral"
    return "uncertain"


def measured(used: list[str], evidence: dict, sentence: str) -> tuple[str | None, bool]:
    """One unambiguous cited M17 verdict. A familiar ID or a look-alike row cannot substitute for provenance."""
    weeks = {int(a or b) for a, b in WEEK.findall(THRESHOLD_WEEK.sub(" ", sentence))}
    selected = []
    covered = set()
    for eid in set(used):
        result = evidence.get(eid) or {}
        source = result.get("source") or {}
        if (result.get("tool") != "finance_kpi" or result.get("status") != "ok"
                or source.get("kind") != "view" or source.get("name") not in VIEWS):
            continue
        for row in result.get("rows") or []:
            if "link" in row and (not weeks or row.get("report_week") in weeks):
                selected.append((source["name"], row["link"]))
                covered.add(row.get("report_week"))
    if (not weeks <= covered or not selected or len(set(selected)) != 1
            or selected[0][1] not in (None, "link", "no_link")):
        return None, False
    return selected[0][1], True


def problems(text: str, used: list[str], evidence: dict, *, finance_context: bool = False) -> list[tuple[str | None, str]]:
    """V10-compatible (token, explanation) pairs, shared by every answer surface."""
    # A number slot still names its metric even if the surrounding words omit 'billing'.
    def slot_words(match):
        parsed = slots.find_slots(match.group(0))
        finance = any(s.field in ("invoices_billed", "billed_sdr", "billed_wow_pct", "billed_wow_change_sdr") for s in parsed)
        return " billing value " if finance else " value "
    text = normal(slots.SLOT_RE.sub(slot_words, text))
    out = []
    previous_traffic = previous_finance = False
    for sentence in SENTENCES.split(text):
        if not sentence.strip():
            continue
        has_traffic, has_finance = bool(TRAFFIC.search(sentence)), bool(FINANCE.search(sentence))
        if REFERENT.search(sentence):
            if previous_traffic and has_finance:
                sentence += " (suez)"
            if previous_finance and has_traffic:
                sentence += " (billing)"
        if finance_context and not has_finance and has_traffic and (CAUSE.search(sentence) or ASSOCIATION.search(sentence)
                                                or INSUFFICIENT.search(sentence)):
            sentence += " (billing)"
        previous_traffic, previous_finance = has_traffic, has_finance
        # Keep both domains in scope across a contrast, but do not carry a negation into its second clause.
        clauses = re.split(r"\b(?:but|however|yet)\b|ولكن|لكن", sentence)
        for clause in clauses:
            # Only a clause that states a relation (or points back with "this / it") inherits both domains;
            # "transits averaged 35.6, but …" stays the independent traffic fact it is.
            if (len(clauses) > 1 and TRAFFIC.search(sentence) and FINANCE.search(sentence)
                    and any(p.search(clause) for p in (CAUSE, ASSOCIATION, NEGATIVE, INSUFFICIENT, REFERENT))):
                clause = f"{clause} (billing suez)"
            kind = classify(clause.strip())
            if kind == "neutral":
                continue
            verdict, valid = measured(used, evidence, clause)
            if kind == "causal":
                reason = "M17 never establishes that Suez traffic or news caused a billing change"
            elif kind == "uncertain":
                reason = "ambiguous traffic/billing claim: separate independent facts or use the fixed M17 wording"
            elif MONEY.search(clause) or NEWS.search(clause):
                reason = "M17 measures invoice counts against Suez transits, not monetary amounts or news effects"
            elif not valid:
                reason = "cite one unambiguous finance_kpi traffic_link result from its KPI view for this claim"
            elif (kind, verdict) in (("association", "link"), ("negative", "no_link"), ("insufficient", None)):
                continue
            else:
                reason = f"the claim disagrees with the cited M17 verdict ({verdict or 'too few weeks'})"
            hint = wording(verdict, "ar" if re.search(r"[\u0600-\u06ff]", clause) else "en") if valid else ""
            out.append((kind, f"{reason}. {hint}".strip()))
    return out


def traffic_ids(evidence: dict) -> list[str]:
    """The ids of the run's own M17 results, by provenance (tool, status, KPI view) — never by a familiar id."""
    return [eid for eid, r in evidence.items()
            if (r or {}).get("tool") == "finance_kpi" and r.get("status") == "ok"
            and (r.get("source") or {}).get("kind") == "view" and (r.get("source") or {}).get("name") in VIEWS]


def _repair(text: str, used: list[str], evidence: dict, *, append: bool) -> tuple[str, list[str]] | None:
    """`text` without its refused traffic/billing sentences, the fixed M17 wording in their place. None = it cannot
    be repaired (no single measured verdict in the run), so the caller's check stops the run as before."""
    ids = traffic_ids(evidence)
    verdict, valid = measured(ids, evidence, "")
    if not valid:
        return None
    fixed = wording(verdict, "ar" if re.search(r"[؀-ۿ]", text) else "en")
    used = [*used, *(i for i in ids if i not in used)]
    if not append:                                   # a caveat: one short statement, replaced whole
        return fixed, used
    kept = " ".join(u for u in _units(text) if not problems(u, used, evidence)).rstrip(" ;؛")
    if kept and kept[-1] not in ".!?؟":
        kept += "."
    out = f"{kept} {fixed}".strip() if fixed not in kept else kept
    return (fixed if problems(out, used, evidence) else out), used


def _units(text: str) -> list[str]:
    """Whole sentences and `;` parts as the reader sees them; a `;` or `.` inside brackets does not split."""
    out, depth, start = [], 0, 0
    for match in UNITS.finditer(text):
        token = match.group(0)
        if token == "(":
            depth += 1
        elif token == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(text[start:match.start()])
            start = match.end()
    return [u for u in [*out, text[start:]] if u.strip()]


def repair_notes(notes: dict, evidence: dict) -> tuple[dict, list[str]]:
    """The model's notes with every refused traffic/billing sentence replaced by the fixed M17 wording of the run's
    own verdict (code, no model call). Returns the notes and one line per repaired note; a note that cannot be
    repaired is left as written, and `note_problems` then stops the run. Why: in the Phase 6 acceptance run (tl1)
    one refused sentence cost the week's whole pack — 7 of 11 golden weeks — while the rest of the notes were sound."""
    notes, done = {**notes}, []
    for section, field in (("summary", "text"), ("drivers", "explanation"), ("context", "text")):
        items = [dict(n) for n in notes.get(section) or []]
        for i, note in enumerate(items):
            ids = note.get("evidence_ids") or []
            if problems(note[field], ids, evidence) and (fix := _repair(note[field], ids, evidence, append=True)):
                note[field], note["evidence_ids"] = fix
                done.append(f"insight_notes V10: {section}[{i}] traffic/billing sentence → the fixed M17 wording")
        if items:
            notes[section] = items
    caveats, ids = list(notes.get("caveats") or []), traffic_ids(evidence)
    for i, text in enumerate(caveats):
        if problems(text, ids, evidence) and (fix := _repair(text, ids, evidence, append=False)):
            caveats[i] = fix[0]
            done.append(f"insight_notes V10: caveats[{i}] traffic/billing sentence → the fixed M17 wording")
    if caveats:
        notes["caveats"] = caveats
    return notes, done


def note_problems(notes: dict, evidence: dict) -> list[str]:
    out = []
    for section, field in (("summary", "text"), ("drivers", "explanation"), ("context", "text")):
        for i, note in enumerate(notes.get(section) or []):
            out += [f"{section}[{i}]: {message}" for _, message in
                    problems(note[field], note.get("evidence_ids") or [], evidence)]
    for i, text in enumerate(notes.get("caveats") or []):
        # caveats are plain strings with no ids: judged against the run's own M17 results (by provenance)
        out += [f"caveats[{i}]: {message}" for _, message in problems(text, traffic_ids(evidence), evidence)]
    return out
