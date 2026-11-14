"""Test mode for the web's end-to-end tests (Frontend plan §10.4, F0): the real API over the real databases, with a
scripted model instead of the LLMs (`roles.FakeRoles`), so the browser tests spend no model quota.

Started only by `Serve.py --fake-roles`, which refuses unless `API_FAKE_ROLES=1` is set and the server binds the
loopback (it always does, ADR-064). The script: a finance question → `finance_kpi` for the week named in the question
(default 23) → an answer whose numbers are slots, so the web's number receipts are real; any other question → one
`not_in_data` answer. Structured roles (views, route advice, the watch brief) are not scripted: those runs fail as
`output_invalid`, which the UI must show calmly anyway.
"""
import re
from typing import Any, cast

from langchain_core.messages import AIMessage, ToolMessage

from pipelines.agents import roles
from pipelines.agents.graphs import supervisor as sv
from pipelines.api.app import create_app

WEEK_RE = re.compile(r"\b(?:week|W|أسبوع)\s*(\d{1,2})\b", re.I)


class WebFake:
    def __call__(self, role, msgs, tools, schema):
        if schema is not None:
            return {}                                  # not scripted: fails validation → output_invalid
        names = {getattr(t, "name", None) or (t.get("name") if isinstance(t, dict) else None) for t in tools or []}
        done = [m for m in msgs if isinstance(m, ToolMessage) and m.name not in (sv.SKILL_TOOL, sv.ANSWER_TOOL)]
        question = next((str(m.content) for m in msgs if getattr(m, "type", "") == "human"), "")
        if not done and "finance_kpi" in names:
            m = WEEK_RE.search(question)
            week = int(m.group(1)) if m and 1 <= int(m.group(1)) <= 52 else 23
            return AIMessage(content="", tool_calls=[{"name": "finance_kpi", "id": "web",
                                                      "args": {"report_week": week, "dataset": "weekly"}}])
        if done and done[-1].name == "finance_kpi":
            return AIMessage(content="", tool_calls=[{"name": sv.ANSWER_TOOL, "id": "a1", "args": {
                "status": "answered", "evidence_ids": ["insight.web"],
                "answer": "PortPilot billed {insight.web:billed_sdr|sdr} that week, against a budget of "
                          "{insight.web:budget_sdr|sdr}; collections were {insight.web:collected_sdr|sdr}."}}])
        return AIMessage(content="", tool_calls=[{"name": sv.ANSWER_TOOL, "id": "a1", "args": {
            "status": "not_in_data", "answer": "This is not in PortPilot's data.", "evidence_ids": []}}])


def create_fake_app():
    """The uvicorn factory of `Serve.py --fake-roles`."""
    script = cast(roles.Script, WebFake())
    return create_app(roles_factory=cast(Any, lambda: roles.FakeRoles(script)))   # a factory, as Api_check passes
