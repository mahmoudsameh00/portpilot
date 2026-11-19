# Pipelines — the runtime

What production runs (ADR-071, ADR-072): the packages `agents/` (graphs, tools, skills, the PPTX deck), `api/`
(FastAPI) and `lib/` (retrieval, uploads, the shared helpers), and the command-line entry points in `scripts/<area>/`.
The API / scheduler image copies this folder, `Data/` and `db/migrations/` only (`ops/docker/api.Dockerfile`).
The scripts that built the data, every check and evaluation, and the run tooling live in `dev/` (`dev/README.md`).

Each script's header says what it reads, what it writes and whether it is safe to re-run. Run from the project root:

```text
uv run python pipelines/scripts/<area>/<stem>.py <command> …
```

| Script | Area | Kind | What it does |
|---|---|---|---|
| `agents/Weekly_pack.py` | agents | A (CLI) | `run --week W --as <Finance manager>` / `show` / `resume --decision approve\|edit\|reject --as <approver>` / `list`: the `weekly_pack` graph on PostgresSaver; a PPTX preview in `reports/_drafts/`, on approval `reports/2025-W<ww>/deck.pptx` + JSON files (git-ignored); ADR-050, ADR-051. Phase 8 (ADR-054): `scheduled` (what Task Scheduler runs: the next week of the replay as `PACK_RUN_AS`, one pending pack at a time, then the retention; `reports/_log/scheduled.jsonl`, a toast), `prune [--dry-run]`, `report` (G5); `run` / `resume` / `scheduled` traced in LangSmith when `LANGSMITH_API_KEY` is set; `resume --request "…" [--yes]` = the manager's request in words (ADR-067) |
| `agents/Voyage_watch.py` | agents | A (CLI) | `run --as <employee> [--as-of]` / `scheduled [--as]` (Task Scheduler, every 12 h, replay clock; `WATCH_RUN_AS`) / `alerts --as [--thread] [--vessel] [--high]` / `show <thread>` / `list` / `prune [--dry-run]`: the `voyage_watch` graph (ADR-058) on PostgresSaver, one thread + one run file `reports/voyage_watch/` per run (30-day retention of the threads); LangSmith with a key; plan §6c |
| `agents/Ask.py` | agents | A (CLI) | `ask "…" --as <employee> [--lang ar] [--as-of …]`: one question — finance, operations or both — to the supervisor (`graphs/supervisor.py`): the code router, the refused part named, numbers filled from the tools; one thread `ask:<employee>:<as_of>:<n>` in agent_state (30-day retention) + a LangSmith trace (`entry:ask`) per question; `show` / `list` (the asker and the CEO), `prune`. Replaced `Finance_qa.py` on 2026-10-29 (Agents plan Phase 12 S4) |
| `agents/Route_advice.py` | agents | A (CLI) | `ask --vessel N \| --type --condition --scnt --from --to --as <employee> [--speed] [--as-of]` / `show <thread>` / `list --as`: the `route_advice` graph (ADR-057) on PostgresSaver, one thread per question (30-day retention); prints the comparison, the advice with its numbers filled, assumptions and sources; LangSmith with a key; plan §6b |
| `agents/Arrival_advice.py` | agents | A (CLI) | `ask --vessel N --as <employee>` / `show` / `list`: the `arrival_advice` graph (Just-in-Time arrival, ADR-070) with the RTA from `port_call_messages`; one thread per question |
| `agents/View.py` | agents | A (CLI) | the "smart" finance view (ADR-066): `--as <employee> --ask "…"` (one structured model call picks from the chart catalogue, a question without a week is asked back) or `--choice '<ViewChoice JSON>'` (code only); `--pptx <file>` draws it as one native-chart slide read back; values from `finance_kpi` as the employee |
| `agents/Checkpointer_setup.py` | agents | A (deployment step) | the LangGraph checkpoint tables in schema `agent_state` (as the owner account, after migration 016; again after a `langgraph-checkpoint-postgres` upgrade); second run = no change |
| `api/Serve.py` | api | A (server) | the PortPilot API (`pipelines/api/app.py`, FastAPI) on 127.0.0.1, one process, `--port` (default 8000); docs at `/docs`; FastAPI plan P0 (health only), ADR-064 |
| `api/Api_admin.py` | api | A (CLI, owner account) | `create` / `reset` / `disable` / `enable --employee N`: the API's logins (one per employee, password asked twice; migration 023) |
| `retrieval/Upload_promotion.py` | retrieval | A (CLI) | promotion requests in `Data/incoming/promotion/` (review / approve / commit); `--selftest` uses a throwaway collection |

The model calls go through `agents/llm.py`: the provider registry (models per role in `agents/models.toml`,
ADR-045; swap procedure `docs/model_swap.md`), the per-minute budget, the persisted daily quota state and the response
cache `Data/processed/agents/eval/llm_cache/` (git-ignored). The retrieval library `lib/` (ADR-039) serves
`search_documents` and the uploads read at inference time (ADR-042–044; the local model `models/onnx/bge-m3`, rebuilt by
`dev/tools/export_onnx.py`).

### Operations (2026-11-17, Staging readiness plan, ADR-071)

`scripts/ops/` holds the deployment's scripts; how to use them is `docs/deploy/RUNBOOK.md`.
- `Scheduler_service.py`: the scheduler container's loop (weekly pack Monday 10:30, voyage watch 10:30 + 22:30
  Africa/Cairo); `--plan`, `--once <job>`.
- `Backup.py`: `backup` / `verify` / `restore` / `secure` / `prune` / `drill` of the three stores and the durable files
  (standard library + the docker CLI: also runs with the VM's `python3`).
- `Migrate.py`: `status` / `apply --yes` over `public.schema_migrations` (migration 031).
- `Deploy_smoke.py`: the smoke test after a deploy (standard library).
- The deployment's rules are checked by `dev/checks/ops/Deploy_check.py` (no database / network / Docker; CI).
