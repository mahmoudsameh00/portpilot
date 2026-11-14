"""The PortPilot API (FastAPI plan, `docs/archive/2026-11-05_FastAPI_plan.md`): the four CLIs' products for a logged-in employee.

One process on 127.0.0.1 (plan §4, owner A2); every graph run goes to a bounded run executor, never inside a request;
RBAC stays inside the tools (ADR-006) — the API only says who asks.
"""
