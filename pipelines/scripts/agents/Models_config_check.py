"""Models config check — `pipelines/agents/models.toml` + `model_config.py` + their use in `llm.py` / `roles.py`.

Plan:    docs/plans/Model_flexibility_plan.md (approved 2026-11-13; owner decisions M1–M7).
Run:     uv run python tools/run.py pipelines/scripts/agents/Models_config_check.py   (from the project root)
Reads:   the tracked models file; temporary TOML files written to a temp folder (removed). No database, no model call,
         no network: Phases 2–3 talk to a stub OpenAI-style server on 127.0.0.1 started by this script.
Writes:  nothing tracked (temp folders, removed).
Re-run:  safe.

Phases
1. The tracked file = ADR-045 (+ amendments 1–2): the roles' models, structured methods, limits, temperature and timeout
   equal what `roles.py` / `llm.PROVIDERS` held before the file; every cache key of the four models is byte-equal to
   the pre-file payload (the existing caches and recorded baselines stay valid); bad files fail with one message that
   names the entry; EVAL_MODELS switches the roles of an evaluation process only and back; a role without any key is
   refused when the real roles are built.
2. Adapters (M2): `openai_compatible` with a generic base_url and `langchain` (init_chat_model) against the stub —
   request shape (model id, messages, the key in the Authorization header, temperature sent / not sent), the model
   list; errors (429 day / minute, 400, 404, 503) classified as before.
3. Robustness (W7, W8, W10): an outage (503 on a model that has not answered in this process) is not counted toward
   a cached failure; a request-specific 5xx (the model answers others) still is, on its second run; a priced model
   stops at its `max_usd_per_day` and the role's fallback answers; the cost per call is in the role's usage record.
Final Checkpoint.
"""
# %% Setup
import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import tomllib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
from langchain_core.utils.function_calling import convert_to_openai_tool  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from pipelines.agents import llm, model_config, roles  # noqa: E402

TRACKED = model_config.DEFAULT_FILE
DONE: list[int] = []


# %% Phase 1 — The tracked file = ADR-045, cache keys unchanged
# What roles.py and llm.PROVIDERS held before models.toml (git 68a8d3b), written here by hand as the reference.
BEFORE_ROLES = {
    "insight": [("gemini", "gemini-3.5-flash-lite", "function_calling"),
                ("openrouter", "nvidia/nemotron-3.5-super-vl:free", "function_calling")],
    "writer": [("gemini", "gemini-3.5-flash-lite", "function_calling"),
               ("openrouter", "nvidia/nemotron-3.5-super-vl:free", "function_calling")],
    "tools": [("gemini", "gemini-3.5-flash-lite", "function_calling"), ("groq", "openai/gpt-oss-20b", "json_schema")],
}
BEFORE_PROVIDERS = {
    "gemini": {"key": "GEMINI_API_KEY", "rpm": 10, "tpm": 250_000, "rpd": None, "scope": "model",
               "day_tz": "America/Los_Angeles",
               "candidates": ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemma-4-31b-it"]},
    "groq": {"key": "GROQ_API_KEY", "rpm": 30, "tpm": 8_000, "rpd": 1_000, "scope": "model", "day_tz": "UTC",
             "candidates": ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]},
    "openrouter": {"key": "OPENROUTER_API_KEY", "rpm": 20, "tpm": 1_000_000, "rpd": 50, "scope": "provider",
                   "day_tz": "UTC", "base_url": "https://openrouter.ai/api/v1",
                   "candidates": ["nvidia/nemotron-3-super-120b-a12b:free", "thinkingmachines/inkling:free",
                                  "poolside/laguna-s-2.1:free"]},
}
FOUR = [("gemini", "gemini-3.5-flash-lite"), ("groq", "qwen/qwen3.8-27b"), ("groq", "openai/gpt-oss-20b"),
        ("openrouter", "nvidia/nemotron-3.5-super-vl:free")]


def legacy_key(provider, model, messages, tools=None, schema=None, method=None) -> str:
    """`llm.LLM.key` as written before models.toml (params = {} for every role call)."""
    payload = {"provider": provider, "model": model, "params": {},
               "messages": [llm.canonical(m) for m in messages],
               "tools": [convert_to_openai_tool(t) for t in tools or []],
               "schema": schema.model_json_schema() if schema else None, "method": method}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
                          .encode("utf-8")).hexdigest()


class Probe(BaseModel):
    passed: bool
    problems: list[str] = []


@tool
def finance_kpi(report_week: int, dataset: str) -> dict:
    """Weekly finance KPIs (a stand-in with the real tool's name for the key test)."""
    return {}


CONVERSATIONS = [
    [HumanMessage("How much did PortPilot bill in week 23 of 2025?")],
    [SystemMessage("You write the weekly pack."), HumanMessage("كم كانت الفواتير في الأسبوع ٢٣؟")],
    [HumanMessage("q"), AIMessage(content="", tool_calls=[{"name": "finance_kpi", "args": {"report_week": 23,
                                                                                         "dataset": "weekly"},
                                                            "id": "c1"}]),
     ToolMessage(content='{"rows": []}', tool_call_id="c1", name="finance_kpi")],
]

tmp = Path(tempfile.mkdtemp(prefix="models_config_check_"))
try:
    after_roles = {r: [(c.provider, c.model, c.method) for c in cs] for r, cs in roles.ROLES.items()}
    assert after_roles == BEFORE_ROLES, after_roles
    after_providers = {k: {f: v.get(f) for f in BEFORE_PROVIDERS[k]} for k, v in llm.PROVIDERS.items()}
    assert after_providers == BEFORE_PROVIDERS, after_providers
    for provider, model in FOUR:
        p = BEFORE_PROVIDERS[provider]
        assert llm.limits(provider, model) == {k: p[k] for k in ("rpm", "tpm", "rpd", "scope")}, (provider, model)
        kw = llm.chat_kwargs(provider, model)
        assert kw == {"temperature": 0, "max_retries": 0, "timeout": 120}, (provider, model, kw)
    keys_checked = 0
    for provider, model in FOUR:
        m = llm.LLM(provider, model, cache_dir=tmp / "cache", quota=llm.QuotaState(tmp / "quota", counters=None))
        for msgs in CONVERSATIONS:
            for kwargs in ({}, {"tools": [finance_kpi]}, {"schema": Probe, "method": "function_calling"},
                           {"schema": Probe, "method": "json_schema"}):
                assert m.key(msgs, **kwargs) == legacy_key(provider, model, msgs, **kwargs), (provider, model, kwargs)
                keys_checked += 1

    # bad files: one error naming the entry
    good = tomllib.loads(TRACKED.read_text(encoding="utf-8"))

    def broken(change) -> str:
        data = json.loads(json.dumps(good))
        change(data)
        try:
            model_config.parse(data, Path("broken.toml"))
        except model_config.ModelConfigError as e:
            return str(e)
        return "accepted"

    cases = {
        "providers.gemini": lambda d: d["providers"]["gemini"].update(adapter="grpc"),
        "roles.writer": lambda d: d["roles"].update(writer=["flash_lite", "missing_model"]),
        "roles.tools": lambda d: d["roles"].update(tools=[]),
        "models.nemotron": lambda d: d["models"]["nemotron"].update(structured="xml"),
        "models.qwen": lambda d: d["models"]["qwen"].update(max_usd_per_day=1.0),
        "providers.openrouter": lambda d: d["providers"]["openrouter"].pop("base_url"),
        "models.copy": lambda d: d["models"].update(copy=dict(d["models"]["flash_lite"])),
        "models.flash_lite": lambda d: d["models"]["flash_lite"].update(limits={"rpm": 0, "tpm": 1}),
    }
    refused = {name: broken(change) for name, change in cases.items()}
    assert all(name in msg for name, msg in refused.items()), refused

    # EVAL_MODELS (M4): another file for an evaluation process, then back to the tracked one
    swapped = TRACKED.read_text(encoding="utf-8").replace('writer  = ["flash_lite", "nemotron"]',
                                                          'writer  = ["nemotron", "flash_lite"]')
    assert swapped != TRACKED.read_text(encoding="utf-8")
    (tmp / "eval_models.toml").write_text(swapped, encoding="utf-8")
    os.environ["EVAL_MODELS"] = str(tmp / "eval_models.toml")
    try:
        assert roles.use_eval_models() == str(tmp / "eval_models.toml")
        assert roles.ROLES["writer"][0].provider == "openrouter" and roles.ROLES["tools"][0].provider == "gemini"
    finally:
        del os.environ["EVAL_MODELS"]
        roles.reload(None)
    assert {r: [(c.provider, c.model, c.method) for c in cs] for r, cs in roles.ROLES.items()} == BEFORE_ROLES
    assert roles.use_eval_models() is None

    # a role without any key is refused when the real roles are built (an Exhausted: the API answers 503)
    has_key = llm.has_key
    llm.has_key = lambda provider: provider != "gemini" and provider != "openrouter"
    try:
        roles.Roles(cache_dir=tmp / "cache", quota=llm.QuotaState(tmp / "quota", counters=None))
        no_key = "built"
    except roles.NoModelKey as e:
        no_key = "refused" if "insight" in str(e) and isinstance(e, llm.Exhausted) else str(e)
    finally:
        llm.has_key = has_key
    assert no_key == "refused", no_key
    print(f"Phase 1: roles = ADR-045 ({sum(len(v) for v in BEFORE_ROLES.values())} candidates), providers and the four "
          f"models' limits / temperature / timeout = before; {keys_checked} cache keys byte-equal to the pre-file "
          f"payload; {len(refused)} broken files refused with the entry named; EVAL_MODELS switch and back; keyless "
          f"role refused")
    print("✅ Phase 1 validation passed: models.toml reproduces ADR-045 exactly, cache keys unchanged")
    DONE.append(1)
finally:
    shutil.rmtree(tmp, ignore_errors=True)


# %% Phase 2 — Adapters against a stub OpenAI-style server (M2)
# One local server answers like an OpenAI-compatible endpoint; the behaviour is chosen by the model id. Nothing leaves
# 127.0.0.1. The models file of this phase is a temp copy of the tracked one plus two stub providers and their models.
class _Stub(BaseHTTPRequestHandler):
    seen: list[dict] = []

    def log_message(self, *a):          # quiet
        pass

    def _send(self, code: int, body: dict, headers: dict | None = None):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        _Stub.seen.append({"path": self.path, "auth": self.headers.get("authorization")})
        self._send(200, {"data": [{"id": m} for m in ("stub-ok", "stub-notemp", "stub-ok-lc", "stub-503")]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))))
        _Stub.seen.append({"path": self.path, "auth": self.headers.get("authorization"), "body": body})
        model, last = body.get("model"), str(body["messages"][-1].get("content"))
        if model == "stub-503" or (model == "stub-mixed" and "BAD" in last):
            return self._send(503, {"error": {"message": "upstream overloaded", "type": "server_error"}})
        if model == "stub-day":
            return self._send(429, {"error": {"message": "Rate limit exceeded: free-models-per-day"}})
        if model == "stub-minute":
            return self._send(429, {"error": {"message": "Rate limit reached, requests per minute"}},
                              {"retry-after": "1"})
        if model == "stub-400":
            return self._send(400, {"error": {"message": "invalid request: bad parameter"}})
        if model == "stub-404":
            return self._send(404, {"error": {"message": "model not found"}})
        tokens = (1000, 500) if model == "stub-priced" else (10, 5)
        self._send(200, {"id": "c", "object": "chat.completion", "created": 0, "model": model,
                         "choices": [{"index": 0, "finish_reason": "stop",
                                      "message": {"role": "assistant", "content": f"hello from {model}"}}],
                         "usage": {"prompt_tokens": tokens[0], "completion_tokens": tokens[1],
                                   "total_tokens": sum(tokens)}})


server = ThreadingHTTPServer(("127.0.0.1", 0), _Stub)
threading.Thread(target=server.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{server.server_address[1]}/v1"
STUB_TOML = f'''
[providers.stub]
adapter  = "openai_compatible"
key_env  = "STUB_KEY"
base_url = "{BASE}"
limits   = {{ rpm = 1000, tpm = 10000000, scope = "model" }}

[providers.stublc]
adapter     = "langchain"
key_env     = "STUB_KEY"
lc_provider = "openai"
base_url    = "{BASE}"
limits      = {{ rpm = 1000, tpm = 10000000, scope = "model" }}

[models.s_ok]
provider = "stub"
id = "stub-ok"
structured = "json_schema"
temperature = 0

[models.s_notemp]
provider = "stub"
id = "stub-notemp"
structured = "json_mode"

[models.s_lc]
provider = "stublc"
id = "stub-ok-lc"
structured = "function_calling"
temperature = 0

[models.s_mixed]
provider = "stub"
id = "stub-mixed"
structured = "json_schema"
temperature = 0

[models.s_503]
provider = "stub"
id = "stub-503"
structured = "json_schema"
temperature = 0

[models.s_priced]
provider = "stub"
id = "stub-priced"
structured = "json_schema"
temperature = 0
price_usd_per_mtok = {{ input = 2.0, output = 10.0 }}
max_usd_per_day = 0.02

[models.s_fallback]
provider = "stub"
id = "stub-fallback"
structured = "json_schema"
temperature = 0
'''
tmp2 = Path(tempfile.mkdtemp(prefix="models_config_check_stub_"))
real_sleep = llm.time.sleep
os.environ["STUB_KEY"] = "stub-secret"
try:
    text = TRACKED.read_text(encoding="utf-8")
    text = text.replace("\n[roles]\n", "\n" + STUB_TOML + "\n[roles]\n") \
        .replace('writer  = ["flash_lite", "nemotron"]', 'writer  = ["s_priced", "s_fallback"]')
    (tmp2 / "models.toml").write_text(text, encoding="utf-8")
    roles.reload(tmp2 / "models.toml")
    llm.time.sleep = lambda s: None          # the retry waits of the rules, not of this check
    quota = llm.QuotaState(tmp2 / "quota", counters=None)

    def make(model: str, provider: str = "stub") -> llm.LLM:
        return llm.LLM(provider, model, cache_dir=tmp2 / "cache", quota=quota)

    _Stub.seen.clear()
    ok = make("stub-ok").invoke([HumanMessage("hi")])
    req = _Stub.seen[-1]
    assert ok.ok and llm.message_text(ok.message) == "hello from stub-ok", ok
    assert req["path"] == "/v1/chat/completions" and req["auth"] == "Bearer stub-secret", req
    assert req["body"]["model"] == "stub-ok" and req["body"]["messages"][-1]["content"] == "hi" \
        and req["body"]["temperature"] == 0, req["body"]
    assert "stub-secret" not in json.dumps(ok.__dict__, default=str)            # never in a reply / cache record
    nt = make("stub-notemp").invoke([HumanMessage("hi")])
    assert nt.ok and "temperature" not in _Stub.seen[-1]["body"], _Stub.seen[-1]["body"]      # W4: not sent
    lc = make("stub-ok-lc", "stublc").invoke([HumanMessage("hi")])
    assert lc.ok and _Stub.seen[-1]["body"]["model"] == "stub-ok-lc" and _Stub.seen[-1]["auth"] == "Bearer stub-secret"
    import httpx
    with httpx.Client(timeout=5) as client:
        served = llm.available_models("stub", client)
    assert "stub-ok" in served and _Stub.seen[-1]["path"] == "/v1/models", served
    # the error rules of llm.py, unchanged: a daily 429 marks the model exhausted for the day; a minute 429 gets one
    # retry then stops the model for the run; 400 / 404 are cached as deterministic failures
    errors = {}
    for model in ("stub-day", "stub-minute"):
        try:
            make(model).invoke([HumanMessage("hi")])
            errors[model] = "answered"
        except llm.Exhausted as e:
            errors[model] = "daily" if "daily quota" in str(e) else "stopped" if "stopped" in str(e) or \
                "rate_minute" in str(e) else str(e)[:80]
    for model in ("stub-400", "stub-404"):
        r_ = make(model).invoke([HumanMessage("hi")])
        errors[model] = (r_.error or {}).get("kind")
    assert errors == {"stub-day": "daily", "stub-minute": "stopped", "stub-400": "bad_request",
                      "stub-404": "model_missing"}, errors
    assert quota.state["stub/stub-day"]["day"] == llm.provider_day("stub")
    print(f"Phase 2: openai_compatible (generic base_url) and langchain (init_chat_model) adapters answer the stub; "
          f"the key only in the Authorization header; temperature sent at 0 / not sent when the entry has none; the "
          f"model list read; errors classified as before {errors}")
    print("✅ Phase 2 validation passed: a provider is an entry in models.toml — no code branch per provider")
    DONE.append(2)

    # %% Phase 3 — Outage-aware repeated failures (W7, M7), spend cap (W8, M5), fallback share (W10)
    for attempt in range(2):                  # two "runs" of a model that never answers: an outage, not counted
        try:
            make("stub-503").invoke([HumanMessage("anything")])
        except llm.Exhausted:
            pass
    assert not any(f["model"] == "stub/stub-503" for f in quota.failures.values()), quota.failures
    outage = make("stub-503")
    assert outage._cached(outage.key([HumanMessage("anything")])) is None          # nothing cached
    first = make("stub-mixed")
    assert first.invoke([HumanMessage("good question")]).ok      # the model answers other requests …
    try:
        first.invoke([HumanMessage("BAD long tool result")])
    except llm.Exhausted:
        pass
    second = make("stub-mixed")                                   # … a second run: the same request fails again
    rep = second.invoke([HumanMessage("BAD long tool result")])
    assert rep.error and rep.error["kind"] == "server_error_repeated", rep
    third = make("stub-mixed")
    n_before = len(_Stub.seen)
    assert third.invoke([HumanMessage("BAD long tool result")]).error["kind"] == "server_error_repeated"
    assert len(_Stub.seen) == n_before                            # a cached failure: no request sent

    # W8: 1,000 input + 500 output tokens at 2 / 10 USD per million = 0.007 USD a call; the cap 0.02 is passed by the
    # third call, so the fourth is refused like a quota and the role's fallback answers
    writer = roles.Role("writer", roles.ROLES["writer"], quota, tmp2 / "cache")
    replies = [writer.invoke([HumanMessage(f"draft {i}")]) for i in range(4)]
    models_used = [r_.model for r_ in replies]
    costs = [c.get("cost_usd") for r_ in replies for c in r_.calls]
    assert models_used == ["stub/stub-priced"] * 3 + ["stub/stub-fallback"], models_used
    assert costs[:3] == [0.007, 0.007, 0.007] and replies[3].calls[0]["outcome"].startswith("exhausted"), \
        (costs, replies[3].calls)
    spent = quota.spend("stub", "stub-priced")
    assert abs(spent - 0.021) < 1e-9, spent
    usage = [c for r_ in replies for c in r_.calls]
    share = roles.fallback_share(usage)
    assert share == 0.25, share
    print(f"Phase 3: an outage (no answer in this process) leaves no failure counted or cached; a request-specific 5xx "
          f"is cached on its second run and then sent no more; the priced model spent {spent:.3f} USD and stopped "
          f"at its 0.02 cap, the fallback answered; fallback share of the 4 calls = {share}")
    print("✅ Phase 3 validation passed: outage-aware failures, a daily spend cap, the fallback share measured")
    DONE.append(3)
finally:
    llm.time.sleep = real_sleep
    os.environ.pop("STUB_KEY", None)
    roles.reload(None)
    server.shutdown()
    shutil.rmtree(tmp2, ignore_errors=True)
assert {r: [(c.provider, c.model, c.method) for c in cs] for r, cs in roles.ROLES.items()} == BEFORE_ROLES


# %% Final Checkpoint
# Narrative: pipelines/checkpoints/agents/Models_config_check.md
assert DONE == [1, 2, 3], DONE
print(f"Final Checkpoint: phases {DONE}")
print("✅ Final Checkpoint passed: the models file is the single place of the model per role; any provider is "
      "an entry; outages, spend and fallbacks are handled and measured (Phases 1–3)")
