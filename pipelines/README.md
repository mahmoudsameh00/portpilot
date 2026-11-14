# Pipelines

Every data pipeline of the project is a Python script here (ADR-036). Each script's header says what it reads, what
it writes and whether it is safe to re-run; the Final Checkpoint narrative (every step, its problems, their fixes) is
in `checkpoints/<area>/<stem>.md`. The notebooks they came from are archived in `docs/archive/notebooks/`.

Run one script, or all of them in verification order, from the project root:

```text
uv run python tools/run.py pipelines/scripts/<area>/<stem>.py [--compare]
uv run python tools/run.py all --compare [--from <stem>] [--with-mongo] [--hashseed N]
```

`tools/run.py` prints the ✅ validation lines, the errors and every file it changed or created under
`Data/processed/` and `db/migrations/` (SHA-256 before / after). `--compare` checks the ✅ lines against the archived
notebook's saved outputs.

| Script | Area | Refactor level | What it produces |
|---|---|---|---|
| `structured/ExtractPortsAttributes.py` | structured | A | `ports.csv` (837 ports) |
| `structured/ExtractPortsConnection.py` | structured | A | `port_connections.csv` (19,990 pairs); the table load only with `--insert` on an empty table |
| `synthetic/SyntheticGenerator.py` | synthetic | A | verifies employees / vessels / containers CSVs; checks invoice pricing (ADR-004, ADR-013) |
| `synthetic/Finance_generator.py` | synthetic | phases | `synthetic/finance/` (customers, vessel → customer, payments, weekly budget, the `finance_test` copy) + manifest, `agents/eval/finance_test_answer_key.json`, migration `012_finance_data.sql`; Agents plan §4a; re-run = identical (`--hashseed` checked) |
| `finance/Finance_views_check.py` | finance | phases | nothing (read-only): the `finance` views of migration 013 = an independent pandas reference on all 52 weeks, invariants, hand-check weeks 5 / 16 / 23 / 49 (reviewed snapshot), RBAC matrix + `finance_bi` privileges; Phase 7: the migration 021 columns = their own pandas reference (weekly-pack plan Phase A); Agents plan Phase 2, `docs/finance_metrics.md` |
| `finance/Executive_analysis.py` | finance | phases | `finance/executive_2025/numbers.json` + 7 chart series (read-only on the views, as of 2025-12-28): findings F1–F13, reconciled with `kpi_weekly`, reviewed snapshot; ADR-061, `docs/analysis/financial_intelligence/`; re-run = identical |
| `finance/Executive_charts.py` | finance | phases | `finance/executive_2025/charts/` 13 PNGs from the analysis outputs (no database); drawn totals = `numbers.json`; re-run = identical bytes |
| `finance/Executive_deck.py` | finance | phases | `reports/executive/2025/PortPilot_2025_Financial_Review.pptx` (17 slides, no LLM); every number registered and read back |
| `rag/Documents_registry.py` | RAG | A | `documents.csv` + migration 010 (29 rows); database = mirror check |
| `rag/FBL_chunking.py` … `rag/USCG_ROI_chunking.py` (7) | RAG | B (USCG + one listed patch) | extracted / cleaned / chunks artifacts per source (2,163 chunks) |
| `semi_structured/AIS_EDI_profiling.py` | semi-structured | B | AIS / EDI profiles |
| `semi_structured/AIS_generator.py` | semi-structured | B | synthetic AIS tracks, static records, voyages + manifest |
| `semi_structured/EDI_generator.py` | semi-structured | A | synthetic IFTMIN messages + manifest |
| `semi_structured/MongoDB_loader.py` | semi-structured | B | MongoDB collections (only writer) + a load report per run |

| `retrieval/Provider_smoke_test.py` | retrieval | A | nothing (one tiny call per embedding provider + one rerank call) |
| `retrieval/Golden_set.py` | retrieval | A | `rag/eval/golden_set.jsonl` (frozen: 64 queries + 8 RBAC cases) |
| `retrieval/Golden_facts.py` | retrieval | A | `rag/eval/golden_facts.jsonl` (80 facts for the 40 questions; ADR-040) |
| `retrieval/Embedding_bakeoff.py` | retrieval | A | `rag/eval/bakeoff_results.json` (vectors cached in `Data/embeddings/bakeoff/`, git-ignored, read by later scripts) |
| `retrieval/Embeddings.py` | retrieval | A | `Data/embeddings/gemini-embedding-2/dense_<variant>.parquet` (git-ignored) + `manifest.json` (committed); ADR-037 |
| `retrieval/Qdrant_loader.py` | retrieval | A | Qdrant `nilegate_docs` (the only writer; nothing on disk); ADR-039 |
| `retrieval/Search_index_benchmark.py` | retrieval | A | nothing (exact vs IVF vs Qdrant exact / HNSW on our vectors) |
| `retrieval/Retrieval.py` | retrieval | A | nothing (validates `search_documents`: exactness, RBAC matrix, filters, cache, rate, latency) |
| `retrieval/Evaluation.py` | retrieval | A | `rag/eval/results_<date>.json` (configurations by the ADR-040 rule → ADR-038) |
| `retrieval/Lib_selftest.py` | retrieval | A | nothing (checks `pipelines/lib/`; throwaway Qdrant collection) |
| `retrieval/Upload_fixtures.py` | retrieval | B-style phases | `rag/eval/uploads/fixtures/` (52 cases: historical NileGate documents + attacks), `expected.json`, `upload_questions.jsonl`; `docs/templates/NileGate_document_v1_example.docx` (preserved evidence; current format: `docs/templates/PortPilot_document_v1.md`) |
| `retrieval/Upload_validation.py` | retrieval | B-style phases | `rag/eval/uploads/validation_report.json` (every fixture verdict, corpus false positives 0, PDF / DOCX parity) |
| `retrieval/Upload_eval.py` | retrieval | B-style phases | `rag/eval/uploads/upload_eval_<date>.json` (local model choice, settings, floor, corpus baseline with a session, isolation, latency) |
| `retrieval/Upload_promotion.py` | retrieval | A (CLI) | promotion requests in `Data/incoming/promotion/` (review / approve / commit); `--selftest` uses a throwaway collection |
| `agents/LLM_smoke_test.py` | agents | A | nothing tracked (each provider key: live model list + one tool-calling request, through the response cache) |
| `agents/LLM_bakeoff.py` | agents | phases | `agents/eval/bakeoff_tasks.json` (T1–T4 + LITE + prompts, frozen: `TASKS_SHA256`), `agents/eval/llm_bakeoff_<date>.json` (scores, selection per role); Agents plan §7a |
| `agents/Tools_check.py` | agents | phases | `agents/tool_cache/` (git-ignored; the live PortWatch week 23): the Stage 1 tools of `pipelines/agents/tools/` each against its source, the audit views (migration 015) against the answer key and a Python auditor, the RBAC matrix (100 × 7), the skills; Agents plan Phase 4 §5a |
| `agents/Stage2_tools_check.py` | agents | phases | `agents/tool_cache/marine_weather.jsonl` (git-ignored; the live 2026-09-13 probe, settled): the Stage 2 tools of `pipelines/agents/tools/` — the clock in the run context + the MongoDB reader (Phase 0), `sea_route` vs published distances (1), migration 020 + `vessel_params` (2), `voyage_status` vs the generator on 500 voyages + the cut (3), `marine_weather` offline + live (4), the RBAC matrix 100 × 4 (5); Agents plan Phase 9 §6a, ADR-055 |
| `agents/Route_advice.py` | agents | A (CLI) | `ask --vessel N \| --type --condition --scnt --from --to --as <employee> [--speed] [--as-of]` / `show <thread>` / `list --as`: the `route_advice` graph (ADR-057) on PostgresSaver, one thread per question (30-day retention); prints the comparison, the advice with its numbers filled, assumptions and sources; LangSmith with a key; plan §6b |
| `agents/Route_advice_check.py` | agents | phases | `agents/eval/route_cases.json` (frozen on the first run); check threads `route_advice:check:…` (deleted): the deterministic nodes vs an independent computation (1), route slots (2), the Validator with 64 planted errors (3), the skill (3s), the graph on fake models + PostgresSaver with crash / resume (4), the real model on the 12 cases (5, cached), RBAC + retention (6); Agents plan Phase 10 §6b |
| `agents/Voyage_watch.py` | agents | A (CLI) | `run --as <employee> [--as-of]` / `scheduled [--as]` (Task Scheduler, every 12 h, replay clock; `WATCH_RUN_AS`) / `alerts --as [--thread] [--vessel] [--high]` / `show <thread>` / `list` / `prune [--dry-run]`: the `voyage_watch` graph (ADR-058) on PostgresSaver, one thread + one run file `reports/voyage_watch/` per run (30-day retention of the threads); LangSmith with a key; plan §6c |
| `agents/Voyage_watch_check.py` | agents | phases | `agents/eval/eta_cases.json` + `eta_eval.json` (frozen); check threads `voyage_watch_check:…` (deleted): ETA rules R / N / S / R0 on 126 replayed cuts (1), next-leg points + Suez ahead vs the generator's timeline (2), alert rules on planted storms / traffic drops — precision, recall, sensitivity (3), the brief's Validator with 49 planted errors (4), the skill (4s), the graph on fake models + PostgresSaver, every path, crash / resume (5), the real model once (6, cached), RBAC, contract, the replay planner, firings + retention, the alert reader (7); Agents plan Phase 11 §6c |
| `agents/Checkpointer_setup.py` | agents | A (deployment step) | the LangGraph checkpoint tables in schema `agent_state` (as the owner account, after migration 016; again after a `langgraph-checkpoint-postgres` upgrade); second run = no change |
| `agents/Weekly_pack.py` | agents | A (CLI) | `run --week W --as <Finance manager>` / `show` / `resume --decision approve\|edit\|reject --as <approver>` / `list`: the `weekly_pack` graph on PostgresSaver; a PPTX preview in `reports/_drafts/`, on approval `reports/2025-W<ww>/deck.pptx` + JSON files (git-ignored); ADR-050, ADR-051. Phase 8 (ADR-054): `scheduled` (what Task Scheduler runs: the next week of the replay as `PACK_RUN_AS`, one pending pack at a time, then the retention; `reports/_log/scheduled.jsonl`, a toast), `prune [--dry-run]`, `report` (G5); `run` / `resume` / `scheduled` traced in LangSmith when `LANGSMITH_API_KEY` is set; `resume --request "…" [--yes]` = the manager's request in words (ADR-067) |
| `agents/Scheduler_check.py` | agents | phases | nothing tracked (temp folders; check threads `weekly_pack:check:…`, deleted): the week picker, retention (archive then delete, pending never), scheduled firings end to end on fake models, the run identity + read-only CLI, the tracing contract (no network), the LangSmith read-back (one small trace; only with a key); Agents plan Phase 8 §5e, ADR-054 |
| `agents/Scheduled_outcome_check.py` | agents | phases | temporary logs only, removed; 18 policy cases and 24 actual CLI cases prove exit/log/cron agreement, stopped products and degraded saved output; no DB/network/model calls |
| `agents/Publication_check.py` | agents | phases | temporary packs only, removed; five phases cover atomic publication, DB-sync recovery, locking/integrity, publisher integration and reconciliation authorization; no DB/network/model calls |
| `agents/Langsmith_mirror.py` | agents | phases | nothing local; live (`MIRROR_LIVE=1`): the frozen golden sets as sha-named LangSmith datasets and each evaluation run as an experiment (stored answers + stored code scores, 0 model calls), idempotent, read back; Observability plan S2, ADR-062 amendment 1 |
| `agents/Monitoring_check.py` | agents | phases | nothing tracked (temp folder; 0 network on a recording transport): Sentry off / on, no AI integration, no tracing; a captured exception with its tags and secrets masked; INFO → breadcrumb, WARNING → log, ERROR → event; the weekly pack's cron check-ins and both scheduled CLIs end to end with a failing probe; a Sentry failure never fails a run; Phase 6 live (one event + one log, only with `MONITORING_LIVE=1` + `SENTRY_DSN`); Observability plan S1, ADR-062 |
| `agents/Weekly_pack_check.py` | agents | phases | nothing tracked (temp folders; one PostgreSQL thread, deleted): models + roles, the deterministic nodes on 52 weeks, the fake-model pack on 52 weeks + the approval rules + the PPTX preview / `deck.pptx`, the rewrite routing (patch / whole deck / V8 stop), crash / resume across processes, real models on 4 weeks (only with `PACK_REAL_MODELS=1`; cached), the schema / dataset contract; Agents plan Phases 5–6 §5b / §5c; approver-additions plan Phases 7–9: the approver's own bullets, chart variants (the 26-week trend fetched as the run's user), a revise (note edits / a steer → a re-draft; refusals before any model call; restored on failure) |
| `agents/View.py` | agents | A (CLI) | the "smart" finance view (ADR-066): `--as <employee> --ask "…"` (one structured model call picks from the chart catalogue, a question without a week is asked back) or `--choice '<ViewChoice JSON>'` (code only); `--pptx <file>` draws it as one native-chart slide read back; values from `finance_kpi` as the employee |
| `agents/Views_eval.py` | agents | phases | the views gate (approver-additions plan D6): the frozen 30-question set `agents/eval/views_golden.jsonl` (15 EN + 15 Egyptian AR, its SHA-256 recorded) on the real `tools` role → exact choice ≥ 0.90, ask-back, RBAC leakage 0 → `agents/eval/views_eval_<date>.json` (2026-11-06: 0.9667) |
| `agents/Approver_request_check.py` | agents | phases | nothing tracked (temp folders, InMemorySaver): the manager's request in words (ADR-067) with fake models — each kind → its steps, a mixed request → revise then edit (text read again on the new draft), ask-backs (unplaceable, the week rule, no explicit approve word, two invalid replies), then applied on waiting packs: chart, edit + addition, steer, mixed, stale refused, an unbound number held by the Validator, approve published |
| `agents/Approver_request_eval.py` | agents | phases | the request gate (approver-request plan R4): the frozen 30-request set `agents/eval/approver_request_golden.jsonl` (15 EN + 15 Egyptian AR) on W14's frozen draft `approver_request_draft.json` (both SHA-256 checked); exact ≥ 0.90, AR ≥ EN − 0.10, invented numbers 0 → `approver_request_eval_<date>.json`; `APPROVER_EVAL_OFFLINE=1` = Phase 1 only |
| `agents/Ask.py` | agents | A (CLI) | `ask "…" --as <employee> [--lang ar] [--as-of …]`: one question — finance, operations or both — to the supervisor (`graphs/supervisor.py`): the code router, the refused part named, numbers filled from the tools; one thread `ask:<employee>:<as_of>:<n>` in agent_state (30-day retention) + a LangSmith trace (`entry:ask`) per question; `show` / `list` (the asker and the CEO), `prune`. Replaced `Finance_qa.py` on 2026-10-29 (Agents plan Phase 12 S4) |
| `agents/Finance_qa_check.py` | agents | phases | nothing (fake models, the real Stage 1 tools, no trace): the agent's answer paths (plain text → structured; the answer tool called directly; invalid twice → output_invalid), the answer brief + the 3-round tool cap, the code check + one patch, RBAC (an Operations employee refused), the model-call limit and the records, the CLI; plan §5f F2 (D-P7-6 / D-P7-7) |
| `agents/Deck_check.py` | agents | phases | nothing tracked (previews of weeks 10 / 23 in `Notebooks/_scratch/`): number slots, 52 clean decks through V1–V8, 100 planted wrong numbers (drafts and files), the real failures replayed; Agents plan Phase 6 §5c, ADR-051; Phases 5–6 V9 + layout; Phases 7–8 (approver-additions plan): the approver's bullets through V1–V9 + V8, 132 chart variants read back + 20 planted chart faults (ADR-051 amendment 5) |
| `agents/Golden_weeks.py` | agents | phases | `agents/eval/golden_weeks.json` (the 11 golden weeks by rule, frozen) and `golden_weeks_expected.json` (the evidence of each week, frozen once complete); PortWatch 2025 into `tool_cache/`: Agents plan Phase 7 §5d S1 |
| `agents/Qa_golden.py` | agents | phases | `agents/eval/finance_qa_golden.jsonl` (30 EN + 10 Egyptian Arabic questions, expected values from the tools, frozen): Agents plan Phase 7 §5d S3 |
| `agents/Supervisor_golden.py` | agents | phases | `agents/eval/supervisor_qa_golden.jsonl` (57 items: 21 operations + 10 cross-product + 16 RBAC twins in English, 10 Egyptian Arabic twins; one pinned clock and watch run, expected values from the tools, frozen; 0 model calls): Agents plan Phase 12 §6d S1 |
| `agents/Supervisor_tools_check.py` | agents | phases | read-only check (its route-advice threads deleted): the product tools `watch_alerts`, `fleet_customers`, `route_advice` (the graph as a tool, FakeRoles), the golden contract (every frozen value re-computed as its asker), the RBAC matrix 100 × 4; 0 real model calls: Agents plan Phase 12 §6d S2 |
| `agents/Supervisor_check.py` | agents | phases | read-only check (its route-advice threads deleted): the supervisor's code router on the 57 golden items, the access split, `check_supervisor_answer` on right and planted answers, the agent end to end on scripted fake models, RBAC inside the agent; 0 real model calls: Agents plan Phase 12 §6d S3 |
| `agents/Stage2_eval.py` | agents | phases | the S2 Q&A evaluation on the frozen golden set: inputs hashed, the scorers proven on hand-made states, the harness on fake models (Phases 1–3, 0 calls); `EVAL_REAL_MODELS=1` → two real runs, `agents/eval/stage2_eval_<date>.json` (the Stage 2 baseline) and the done-when verdict (hard gates + completeness EN ≥ 0.85, AR ≥ EN − 0.10): Agents plan Phase 12 §6d S5 |
| `agents/Injection_eval.py` | agents | phases | the prompt-injection evaluation (THREAT_MODEL LLM01): `agents/eval/injection_golden.jsonl` (set v3, 12 items: 2 prompt-leak, 3 role-escalation, 7 planted in a mocked news result, a retrieved document or the asker's own upload; written once per version, hash-asserted; REFREEZE v2 → v3 2026-11-04, FastAPI plan P5), the scorers on hand-made states, the router and the screening without a model (Phases 1–3, 0 calls); `EVAL_REAL_MODELS=1` → two real runs, `agents/eval/injection_eval_<date>.json` and the hard gates (prompt leak 0, planted instruction followed 0, finance leak 0, escalations refused, known-shape planted rows flagged): hygiene follow-ups plan F2 |
| `agents/Memory_golden.py` | agents | phases | `agents/eval/memory_golden.jsonl` (22 dialogs, 15 EN + 7 Egyptian Arabic, 25 follow-ups; frozen 2026-11-04 after the owner's review, hash-asserted; `--review` writes `Notebooks/_scratch/memory_golden_review.md` only): FastAPI plan §6a / P6m |
| `agents/Memory_check.py` | agents | phases | Phases 1–3 nothing (0 calls): `memory.frame_of` on hand-made states, the 25 frozen follow-ups through `memory.resolve`, the model rewrite's guard; Phase 4 with `EVAL_REAL_MODELS=1`: the 22 dialogs through the API on the real models (two runs, `llm_cache/memory_r<k>/`), the §6a.4 gates + resolution primary → `agents/eval/memory_eval_<date>.json`; its threads / conversations / tokens / temporary logins deleted: FastAPI plan P6m, ADR-065 |
| `agents/Stage1_eval.py` | agents | phases | Phases 1–4: nothing (frozen inputs, scorer self-tests, golden weeks + Q&A with fake models, 0 calls); Phase 5 with `EVAL_REAL_MODELS=1`: `agents/eval/stage1_eval_<date>.json` (the baseline, ADR-052) + decks in `Notebooks/_scratch/stage1_eval/`: Agents plan Phase 7 §5d S5–S6; `EVAL_TRACE=1` traces each pack / question in LangSmith (Phase 8, off by default) |
| `api/Serve.py` | api | A (server) | the PortPilot API (`pipelines/api/app.py`, FastAPI) on 127.0.0.1, one process, `--port` (default 8000); docs at `/docs`; FastAPI plan P0 (health only), ADR-064 |
| `api/Load_test.py` | api | phases | nothing tracked (a temp folder; counter rows `loadtest/<run>…` in `agent_state`, deleted): the LLM state shared across processes with fake models — C1 4 × 50 requests vs 120 / day → exactly 120 sent; C2 3 × 3 at 4 / minute → all sent, ≤ 4 per minute; C3 8 × 200 cache lines + 8 × 50 tool-cache lines, none lost or doubled; C4 20 identical requests → 1 provider call; C6 pool sizes from `.env` and the connection budget; ≈ 4 min (C2 waits for real minutes); FastAPI plan P2 |
| `api/Api_smoke.py` | api | phases | the real smoke (only with `API_SMOKE=1`; real models, ≈ 10–15 flash-lite requests): the server in its own process, sign-in, an English and an Egyptian Arabic finance question over SSE, an upload and a question about it, a route advice; its logins / threads / conversations / audit rows deleted at the end; FastAPI plan P7 |
| `api/Api_check.py` | api | phases | nothing tracked (TestClient in process; 7 throw-away logins + their tokens and audit rows, created and deleted with the owner account): Phase 0 the skeleton; 1 auth (token hashed, same 401 for unknown email / wrong password, lockout, sign-out, expiry, disabled, audit rows, `health/ready`); 2 `/me` of 7 profiles = ADR-006 by hand; 3 every error of plan §7 as problem+json; 4 the SSE event contract (fake models; the API's answer = `sv.ask`); 5 C5 / C7–C9 back-pressure, 50 questions at once, cross-employee isolation; 6 uploads (fixtures' verdicts over HTTP, the upload reaching the question as `untrusted_upload` rows, owner-only, promotion); 9 security headers, request id, docs CSP, CORS; 7 the weekly pack on a test thread `weekly_pack:apicheck:…` + a temp reports folder (show, preview, 403s, edit, approve → deck, 409); 8 route advice as a run + the watch's saved alerts and runs; its `ask:` / pack / route threads and promotion folder deleted at the end; 10 / 10; ≈ 3 min |

The agents scripts (Agents plan, Phase 0) are not in `run.py all` either (free LLM APIs with daily quotas). They use
`pipelines/agents/llm.py`: the provider registry (Gemini / Groq / OpenRouter), the model factory (LangChain chat
models, temperature 0, no library retries), the per-minute `Budget`, the persisted daily quota state and the response
cache `Data/processed/agents/eval/llm_cache/` (git-ignored): a re-run makes 0 calls, a quota-exhausted model waits for
the provider's next day; no data guard (all project data is synthetic or public, ADR-037 amendment 2).

The retrieval scripts are not in `run.py all` (they call paid / rate-limited APIs or need `ports-qdrant`). They share
`pipelines/lib/` (ADR-039): `common`, `chunks`, `embeddings`, `qdrant_store`, `evaluation` (ADR-040: retrieval /
ranking / context metrics), and for documents uploaded at inference time (RAG plan Phase 8): `upload_reader`
(PDF / DOCX reading in a child process, file-level and hidden-text findings), `screening` (injection patterns),
`uploads` (the "PortPilot Document v1" shape, `validate_upload`, chunking), `local_embeddings` (ONNX Runtime model),
`session_store` (conversation-only uploads in memory, the session lane, promotion requests). The local ONNX model
(`bge-m3`, the session lane, ADR-043) is exported once by `tools/export_onnx.py` into `models/onnx/` (git-ignored); the
two rejected candidates were removed at the plan's close and `Upload_eval.py` reuses their recorded rows.

- **Level A**: rewritten by hand as functions and `main()`; exploration prints became assertions. Proof: the local run
  (`--compare`: the notebook's ✅ lines kept in order, new ones allowed; `files changed: 0`).
- **Level B**: generated by `uv run python tools/nb_to_script.py clean <stem>` from the archived notebook: the phase
  structure is the flow and stays linear (`# %% <Phase title>` sections, narrative as comments); only Jupyter's
  display rules became `print()`. Proof: `uv run python tools/nb_to_script.py check` (AST equal to the notebook) plus
  the local run.

`all` skips `MongoDB_loader` unless `--with-mongo` (each run reloads MongoDB and adds a load report; keep only the
newest report: its `load_run` is stamped on every document). `--hashseed N` fixes `PYTHONHASHSEED`: two runs with
different seeds that change a file reveal an output that depends on string-hash order (2026-10-01: none left).

Order of `run.py all`: smallest first; `LPI_methodology_chunking` before `LPI_Connecting_to_Compete_chunking` (it reads
its units); the generators before `MongoDB_loader`.

### API integration isolation (2026-11-12)

`scripts/api/Api_integration_check.py` runs authentication, ownership, replay, grants, locks and publication
transactions on a fresh disposable PostgreSQL fixture. The owner wrapper is `ops/tests/run_api_integration.ps1`;
CI has an independent `api-integration` job. `--guard-only` runs directly without a database. The historical
`Api_check.py` requires an explicit isolated full-data clone and creates its own employee identities. See
`docs/api/integration_testing.md`; owner-run database phases passed 5/5 on 2026-11-12. Pushed CI and full-data
acceptance remain pending; evidence is `db/audit/2026-11-12_api_integration_report.txt`.
