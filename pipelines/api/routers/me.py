"""Who am I, and what may I use (plan §3.1). Every flag is computed from the RBAC the tools apply (ADR-006,
`context.permitted` over the supervisor's `TOOL_RESOURCES`) and the pack's own approver rule — nothing is a second,
hand-written copy of the rules."""
from fastapi import APIRouter

from pipelines.agents.graphs import supervisor, weekly_pack
from pipelines.agents.tools import context
from pipelines.api.auth import Signed
from pipelines.api.schemas import Me, Products
from pipelines.lib.retrieval import User

router = APIRouter(tags=["me"])


def me_of(user: User) -> Me:
    tools = sorted(t for t, res in supervisor.TOOL_RESOURCES.items() if context.permitted(user, *res))
    finance = context.permitted(user, context.FINANCE_VIEWS)
    # the pack graph's own approver rule (checked again by the graph at the decision; here it only shapes the UI)
    decide = finance and weekly_pack.approver_check(user.employee_id)[0]
    products = Products(ask=True, packs_read=finance, packs_decide=decide,
                        route_advice="route_advice" in tools, voyage_watch="watch_alerts" in tools,
                        arrival_advice="arrival_advice" in tools, uploads=True)
    return Me(employee_id=user.employee_id, role=user.role, department=user.department, ceiling=user.ceiling,
              tools=tools, products=products)


@router.get("/me", response_model=Me)
def me(p: Signed) -> Me:
    return me_of(p.user)
