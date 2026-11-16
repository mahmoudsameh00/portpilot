"""LLM access for the agents (Agents plan Phase 0, §7a): provider registry, model factory, rate budget, response cache.

- Providers: free APIs only (D1) — Google AI Studio, Groq, OpenRouter (its OpenAI-compatible endpoint). The models are
  the LangChain chat classes the agents will use, with temperature 0 and **max_retries=0**: retries are decided here,
  never inside the client library.
- Data policy (ADR-037 amendment 2, owner 2026-10-14): no data guard — every dataset of this educational project is
  synthetic or public, so the providers are used as if they were paid tiers.
- Response cache: key = SHA-256 of everything sent (provider, model, parameters, messages, tool schemas, structured
  output schema + method). One append-only JSONL per model under Data/processed/agents/eval/llm_cache/ (git-ignored);
  a re-run makes 0 calls. Deterministic failures (bad request, unknown model, a request larger than the per-minute
  token limit) are cached too; quota, rate-limit,
  network and auth failures are not; a server error (5xx) on the same request in REPEATED_SERVER_RUNS separate runs,
  each after its retry, counts as deterministic (`server_failures.json`) and is cached.
- Quota rules (fixed before any run): a local per-minute Budget (requests + tokens); a persisted daily request count
  per provider day that refuses a call once the provider's daily limit is reached (OpenRouter: 50 / day across all
  free models; Groq: 1,000 / day per model); a daily-quota 429 marks the model exhausted until the provider's day
  ends (no retry loop); a per-minute 429 or a transient error gets one wait (<= MAX_RATE_WAIT_S) and one retry, then
  the model stops for this run.
- Several processes at once (FastAPI plan C1–C4, 2026-11-04): the daily count is reserved before each attempt in
  PostgreSQL and the per-minute budget is shared there (`shared_quota`, when the checkpointer login is configured;
  else the files, under a lock); cache lines are appended under a file lock and other processes' new lines are read
  on a miss; the same request at the same moment is sent once (single-flight), the others read its cached reply.
- Secrets: keys go only into the client objects or request headers, never into a URL, a cache key or a log line;
  every error text passes through `redact()`.
- Models and providers (Model flexibility plan, 2026-11-15): read from `pipelines/agents/models.toml` through
  `model_config` — the adapter, key variable and quota day per provider; the limits, temperature, timeout and
  structured-output method per model. A provider is an entry, not a code branch (M2). The cache key payload is unchanged
  for a model with temperature 0 (today's four), so existing caches and recorded baselines stay valid.
"""
import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any, cast

import httpx
from langchain_core.messages import AIMessage, BaseMessage, message_to_dict, messages_from_dict
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel

from pipelines.agents import model_config, shared_quota
from pipelines.lib import shared_files
from pipelines.lib.common import project_root, redact
from pipelines.lib.embeddings import Budget, est_tokens

EVAL_DIR = project_root() / "Data" / "processed" / "agents" / "eval"
CACHE_DIR = EVAL_DIR / "llm_cache"                  # git-ignored
TIMEOUT_S = 120
MAX_RATE_WAIT_S = 60                                # longest single wait on a per-minute limit
OUTPUT_RESERVE_TOKENS = 1_500                       # counted against the token budget before the reply is known
REPEATED_SERVER_RUNS = 2                            # runs in which one request fails with 5xx before it is cached as failed
RECENT_OK_S = 1_800                                 # W7 / M7: "the model answered another request" = within 30 min here
_LAST_OK: dict[str, float] = {}                     # model name → monotonic time of its last fresh answer (this process)

# The providers come from models.toml: adapter, key variable, quota day, base URL, the default limits of a model without
# its own entry (bake-off candidates) and the bake-off candidates. Kept as a dict so the bake-off scripts and the load
# test (which adds a stub provider) read it as before; `limits()` is what the quota code uses.
PROVIDERS: dict[str, dict] = {}


def reload_providers() -> None:
    """Rebuild PROVIDERS from the current models file (after `model_config.use`, evaluation scripts only)."""
    PROVIDERS.clear()
    PROVIDERS.update({k: dict(v) for k, v in model_config.current().providers.items()})


reload_providers()


def limits(provider: str, model: str) -> dict:
    """rpm, tpm, rpd (None = no local daily stop) and scope ("model" | "provider") of one model: its own entry in
    models.toml, else its provider's defaults."""
    e = model_config.model_for(provider, model)
    if e is not None:
        return e.limits
    p = PROVIDERS[provider]
    return {"rpm": p["rpm"], "tpm": p["tpm"], "rpd": p.get("rpd"), "scope": p.get("scope", "model")}


def cost_usd(provider: str, model: str, usage: dict | None) -> float:
    """W8 / M5: the price of one fresh call from its token usage and the entry's hand-entered prices (0 for a free
    model, a cached reply or a model without an entry)."""
    e = model_config.model_for(provider, model)
    if e is None or e.price_in is None or not usage:
        return 0.0
    return round(((usage.get("input_tokens") or 0) * e.price_in
                  + (usage.get("output_tokens") or 0) * (e.price_out or 0)) / 1e6, 6)


class Exhausted(RuntimeError):
    """The model cannot be called now: daily quota reached, stopped for this run, or the key was refused."""


def has_key(provider: str) -> bool:
    return bool(os.environ.get(PROVIDERS[provider]["key"]))


def provider_day(provider: str) -> str:
    """The provider's current quota day (Gemini resets at midnight Pacific time, the others at midnight UTC)."""
    return datetime.now(ZoneInfo(PROVIDERS[provider]["day_tz"])).date().isoformat()


def slug(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", model)


# --- live model lists (no generation quota is spent) ---------------------------------------------------------------

def available_models(provider: str, client: httpx.Client) -> set[str]:
    """Model ids the provider serves right now (a vanished candidate is skipped and reported by the caller)."""
    key = os.environ[PROVIDERS[provider]["key"]]
    if PROVIDERS[provider]["adapter"] == "gemini":
        out, token = set(), None
        while True:
            r = client.get("https://generativelanguage.googleapis.com/v1beta/models",
                           headers={"x-goog-api-key": key}, params={"pageSize": 1000, **({"pageToken": token} if token else {})})
            _raise_for(provider, r)
            js = r.json()
            out |= {m["name"].removeprefix("models/") for m in js.get("models", [])
                    if "generateContent" in m.get("supportedGenerationMethods", [])}
            token = js.get("nextPageToken")
            if not token:
                return out
    base = PROVIDERS[provider].get("base_url")
    if not base:
        raise RuntimeError(f"{provider}: no base_url in models.toml, so no model list")
    r = client.get(base.rstrip("/") + "/models", headers={"Authorization": f"Bearer {key}"})
    _raise_for(provider, r)
    return {m["id"] for m in r.json()["data"]}


def openrouter_key_info(client: httpx.Client) -> dict:
    """OpenRouter's view of the key: is_free_tier (no credits bought: 50 free requests / day), usage, limit."""
    r = client.get("https://openrouter.ai/api/v1/key",
                   headers={"Authorization": f"Bearer {os.environ[PROVIDERS['openrouter']['key']]}"})
    _raise_for("openrouter", r)
    d = r.json().get("data", {})
    return {k: d.get(k) for k in ("is_free_tier", "usage", "limit", "limit_remaining")}


def _raise_for(provider: str, r: httpx.Response) -> None:
    if r.status_code != 200:
        raise RuntimeError(redact(f"{provider} HTTP {r.status_code}: {' '.join(r.text.split())[:300]}"))


# --- model factory ----------------------------------------------------------------------------------------------------

def chat_kwargs(provider: str, model: str, **params) -> dict:
    """What every client gets: no library retries, the model's timeout and temperature (models.toml; a model without
    an entry: 120 s and 0, as before; an entry without `temperature` sends none — W4)."""
    e = model_config.model_for(provider, model)
    temperature = e.temperature if e is not None else 0
    common: dict = {**({"temperature": temperature} if temperature is not None else {}), "max_retries": 0,
                    "timeout": e.timeout_s if e is not None else TIMEOUT_S}
    return {**common, **params}


def chat_model(provider: str, model: str, **params):
    """The LangChain chat model for one candidate, built by its provider's adapter (models.toml)."""
    p = PROVIDERS[provider]
    key = os.environ[p["key"]]
    common = chat_kwargs(provider, model, **params)
    adapter = p.get("adapter")
    if adapter == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, google_api_key=key, **common)
    if adapter == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model=model, api_key=cast(Any, key), **common)
    if adapter == "openai_compatible":          # OpenRouter, OpenAI, Together, DeepSeek, a local Ollama / vLLM server…
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, api_key=cast(Any, key), base_url=p["base_url"], **common)
    if adapter == "langchain":                  # any provider whose LangChain package is installed (M6: `uv add` first)
        from langchain.chat_models import init_chat_model
        return init_chat_model(model, model_provider=p["lc_provider"], api_key=key,
                               **({"base_url": p["base_url"]} if p.get("base_url") else {}), **common)
    raise ValueError(f"{provider}: unknown adapter {adapter!r}")


# --- error classification -------------------------------------------------------------------------------------------

DAY_RE = re.compile(r"per.?day|PerDay|\bRPD\b|\bTPD\b|daily|free-models-per-day", re.I)
TOO_LARGE_RE = re.compile(r"request too large|reduce your message size|context_length_exceeded", re.I)


def _chain(exc: BaseException | None) -> list[BaseException]:
    out, seen = [], set()
    while exc is not None and id(exc) not in seen:
        out.append(exc)
        seen.add(id(exc))
        exc = exc.__cause__ or exc.__context__
    return out


def classify(exc: BaseException) -> tuple[str, float | None]:
    """(kind, provider-requested wait in seconds). Kinds: too_large, quota_day, rate_minute, auth, model_missing,
    bad_request, transient, unknown. Looks through the whole exception chain (LangChain wraps the provider SDK errors)."""
    chain = _chain(exc)
    text = " ".join(f"{type(e).__name__}: {e}" for e in chain)
    status = None
    wait = None
    for e in chain:
        for attr in ("status_code", "code", "status"):
            v = getattr(e, attr, None)
            if isinstance(v, int) and 100 <= v < 600:
                status = status or v
        resp = getattr(e, "response", None)
        ra = getattr(getattr(resp, "headers", None), "get", lambda *_: None)("retry-after")
        if ra and wait is None:
            try:
                wait = float(ra)
            except ValueError:
                pass
    m = re.search(r"retryDelay['\"]?:\s*['\"]?(\d+(?:\.\d+)?)s", text)   # Gemini puts the wait in the body
    if m and wait is None:
        wait = float(m.group(1))
    if status is None:
        m = re.search(r"\b(4\d\d|5\d\d)\b", text)
        status = int(m.group(1)) if m and re.search(r"(?i)error|status|code", text) else None
    names = " ".join(type(e).__name__ for e in chain)
    # one request larger than the per-minute token limit can never pass (Groq answers 429 "Request too large",
    # Phase 5 S6): deterministic, not a wait — cached as a failure so the role falls back at once on every run
    if TOO_LARGE_RE.search(text):
        return "too_large", None
    if status == 429 or "RateLimit" in names or "RESOURCE_EXHAUSTED" in text:
        return ("quota_day" if DAY_RE.search(text) else "rate_minute"), wait
    if status in (401, 403) or "Authentication" in names or "PermissionDenied" in names:
        return "auth", None
    if status == 404 or "NotFound" in names:
        return "model_missing", None
    if status in (400, 422) or "InvalidRequest" in names or "BadRequest" in names:
        return "bad_request", None
    if (status and status >= 500) or re.search(r"Timeout|Connect|ServerError|APIConnection|RemoteProtocol", names):
        return "transient", wait
    return "unknown", None


# --- persisted quota state (shared by every model of the run) -------------------------------------------------------

_AUTO = object()


class QuotaState:
    """Daily request counts and exhausted models, persisted so the rules hold across runs, days and processes.

    FastAPI plan C1: with the checkpointer login configured, the daily count is reserved atomically in PostgreSQL
    before each request (`shared_quota`), so the API and the scheduled CLIs count together; `usage.json` stays as the
    export the reports read. Without it (the CI) the count lives in `usage.json` alone, now read-modify-written under a
    file lock. The exhausted marks and the server-failure runs are re-read from disk on every use (under the lock), so
    a model one process found exhausted is skipped by the others at once."""

    def __init__(self, folder: Path = CACHE_DIR, counters=_AUTO):
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)
        self.usage_file, self.state_file = folder / "usage.json", folder / "quota_state.json"
        self.fail_file = folder / "server_failures.json"
        self.spend_file = folder / "spend.json"          # W8: USD per provider day and model (paid models only)
        self.counters = cast(shared_quota.SharedCounters | None,
                             shared_quota.shared() if counters is _AUTO else counters)

    @property
    def usage(self) -> dict:
        return shared_files.read_json(self.usage_file)

    @property
    def state(self) -> dict:
        return shared_files.read_json(self.state_file)

    @property
    def failures(self) -> dict:
        return shared_files.read_json(self.fail_file)

    def server_failure(self, key: str, model: str, why: str) -> int:
        """Count one run in which this exact request (cache key) still failed with a server error after its retry;
        returns how many runs that is (owner 2026-10-11: the second run turns it into a deterministic failure)."""
        def change(failures: dict) -> int:
            f = failures.setdefault(key, {"model": model, "runs": 0})
            f["runs"] += 1
            f["last"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            f["why"] = why[:300]
            return f["runs"]
        return cast(int, shared_files.update_json(self.fail_file, change)[1])

    @staticmethod
    def scope(provider: str, model: str) -> str:
        return provider if limits(provider, model)["scope"] == "provider" else f"{provider}/{model}"

    def count(self, provider: str, model: str) -> int:
        day, scope = provider_day(provider), self.scope(provider, model)
        if self.counters is not None:
            return self.counters.day_count(scope, day)
        return self.usage.get(day, {}).get(scope, 0)

    def spend(self, provider: str, model: str) -> float:
        """USD spent on this model in the provider's current day (W8)."""
        return float(shared_files.read_json(self.spend_file).get(provider_day(provider), {}).get(f"{provider}/{model}", 0))

    def add_spend(self, provider: str, model: str, usd: float) -> float:
        day, name = provider_day(provider), f"{provider}/{model}"

        def change(spend: dict) -> float:
            d = spend.setdefault(day, {})
            d[name] = round(d.get(name, 0.0) + usd, 6)
            return d[name]
        return cast(float, shared_files.update_json(self.spend_file, change)[1])

    def check(self, provider: str, model: str) -> None:
        """Refuse a model that is exhausted today (no reservation: `reserve` takes the slot just before sending), or
        a paid model that reached its `max_usd_per_day` (M5: stopped like a quota, the fallback answers)."""
        name, day = f"{provider}/{model}", provider_day(provider)
        state = self.state
        if state.get(name, {}).get("day") == day:
            raise Exhausted(f"{name}: daily quota exhausted on {day} ({state[name]['why'][:120]})")
        e = model_config.model_for(provider, model)
        if e is not None and e.max_usd_per_day is not None and self.spend(provider, model) >= e.max_usd_per_day:
            raise Exhausted(f"{name}: daily spend cap reached on {day} ({self.spend(provider, model):.4f} of "
                            f"{e.max_usd_per_day} USD)")
        rpd = limits(provider, model)["rpd"]
        if rpd is not None and self.count(provider, model) >= rpd:
            raise Exhausted(f"{self.scope(provider, model)}: {rpd} requests already sent on {day} (daily limit)")

    def reserve(self, provider: str, model: str) -> int:
        """Take one request of today's quota before sending it (every attempt, as `record` counted each one before);
        the day's count after it, or `Exhausted` when the limit is already reached."""
        day, scope, rpd = provider_day(provider), self.scope(provider, model), limits(provider, model)["rpd"]
        if self.counters is not None:
            seed = self.usage.get(day, {}).get(scope, 0)
            n = self.counters.reserve_day(scope, day, rpd, seed=seed)
            if n is None:
                raise Exhausted(f"{scope}: {rpd} requests already sent on {day} (daily limit, shared counter)")

            def export(usage: dict) -> None:                 # the reports' copy follows the shared number
                d = usage.setdefault(day, {})
                d[scope] = max(d.get(scope, 0), n)
            shared_files.update_json(self.usage_file, export)
            return n

        def take(usage: dict) -> int | None:
            d = usage.setdefault(day, {})
            if rpd is not None and d.get(scope, 0) >= rpd:
                return None
            d[scope] = d.get(scope, 0) + 1
            return d[scope]
        n = shared_files.update_json(self.usage_file, take)[1]
        if n is None:
            raise Exhausted(f"{scope}: {rpd} requests already sent on {day} (daily limit)")
        return cast(int, n)

    def exhaust(self, provider: str, model: str, why: str) -> None:
        m = re.search(r"limit:\s*(\d+)", why)          # Gemini names the free daily limit in its 429 text

        def change(state: dict) -> None:
            state[f"{provider}/{model}"] = {"day": provider_day(provider), "why": why,
                                            "limit": int(m.group(1)) if m else None,
                                            "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        shared_files.update_json(self.state_file, change)

    def daily_limit(self, provider: str, model: str) -> tuple[int | None, int]:
        """(known daily request limit, most requests seen in one provider day): the registry value, else the limit a
        daily-quota 429 named; the second value is a lower bound when no limit is known."""
        st = self.state.get(f"{provider}/{model}", {})
        m = re.search(r"limit:\s*(\d+)", st.get("why", ""))
        known = limits(provider, model)["rpd"] or st.get("limit") or (int(m.group(1)) if m else None)
        seen = max((d.get(self.scope(provider, model), 0) for d in self.usage.values()), default=0)
        return known, seen


# --- the cached model -----------------------------------------------------------------------------------------------

@dataclass
class Reply:
    key: str
    message: AIMessage | None
    error: dict | None                  # {"kind", "text"} for a cached deterministic failure
    cached: bool
    latency_ms: float | None
    usage: dict | None

    @property
    def ok(self) -> bool:
        return self.message is not None


_BUDGETS: dict[str, Budget | shared_quota.SharedBudget] = {}


class _SharedCache:
    """The records of one cache file in this process + the tail that reads other processes' new lines (C3)."""

    def __init__(self, path: Path):
        self.records: dict[str, dict] = {}
        self._tail = shared_files.Tail(path)
        self._lock = threading.Lock()

    def refresh(self) -> None:
        with self._lock:                            # one thread advances the tail at a time
            for rec in self._tail.read():
                self.records[rec["key"]] = rec


_CACHES: dict[Path, _SharedCache] = {}
_CACHES_LOCK = threading.Lock()


def _cache_for(path: Path) -> _SharedCache:
    with _CACHES_LOCK:
        return _CACHES.setdefault(path, _SharedCache(path))


def message_text(m: BaseMessage) -> str:
    return str(m.text)   # langchain-core 1.x: a property (calling it is deprecated); the text blocks only


def canonical(m: BaseMessage) -> dict:
    """What identifies a message in a cache key. A model reply is reduced to its text and tool calls (name + args):
    ids, metadata and provider extras (e.g. Gemini thought signatures, still sent to the provider) can differ after
    a cache round trip and must not change the key of the next turn; a tool result keeps its text and tool name."""
    if isinstance(m, AIMessage):
        return {"type": "ai", "text": message_text(m),
                "tool_calls": [{"name": c["name"], "args": c["args"]} for c in m.tool_calls]}
    if m.type == "tool":
        return {"type": "tool", "name": getattr(m, "name", None), "text": message_text(m)}
    return {"type": m.type, "text": message_text(m)}


class LLM:
    """One candidate model behind the response cache and the quota rules."""

    def __init__(self, provider: str, model: str, params: dict | None = None, cache_dir: Path = CACHE_DIR,
                 quota: QuotaState | None = None):
        self.provider, self.model, self.params = provider, model, params or {}
        self.name = f"{provider}/{model}"
        self.cache_file = cache_dir / provider / f"{slug(model)}.jsonl"
        # one in-memory copy per cache file and process, shared by every LLM object of that model (the API builds
        # its roles per question: a new object must not re-read the file, and one run's `stopped` must not outlive it)
        self._shared = _cache_for(self.cache_file)
        self.cache = self._shared.records
        self._refresh()
        self.quota = quota or QuotaState(cache_dir)
        scope = QuotaState.scope(provider, model)
        p = limits(provider, model)
        # the cache key's params: unchanged for temperature 0 (every model before models.toml), so old caches still
        # match; a model with another temperature (or none sent) gets it in its key
        e = model_config.model_for(provider, model)
        self.key_params = self.params if e is None or e.temperature == 0 else {"temperature": e.temperature,
                                                                                **self.params}
        if self.quota.counters is not None:      # C2: one per-minute budget for every process
            self.budget = _BUDGETS.setdefault(f"shared:{scope}", shared_quota.SharedBudget(
                self.quota.counters, scope, p["rpm"], p["tpm"]))
        else:
            self.budget = _BUDGETS.setdefault(scope, Budget(p["rpm"], p["tpm"]))
        self.stopped: str | None = None
        self.calls = self.hits = 0
        self._chat = None

    def key(self, messages: list[BaseMessage], tools=None, schema: type[BaseModel] | None = None,
            method: str | None = None) -> str:
        payload = {"provider": self.provider, "model": self.model, "params": self.key_params,
                   "messages": [canonical(m) for m in messages],
                   "tools": [convert_to_openai_tool(t) for t in tools or []],
                   "schema": schema.model_json_schema() if schema else None, "method": method}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
                              .encode("utf-8")).hexdigest()

    def invoke(self, messages: list[BaseMessage], *, tools=None,
               schema: type[BaseModel] | None = None, method: str | None = None) -> Reply:
        """One request (or its cached reply). With `schema`, the raw AIMessage is returned and cached; parse it with
        `parse_structured` (the same parser for fresh and cached replies)."""
        assert not (tools and schema), "tools and a structured-output schema are separate requests"
        key = self.key(messages, tools, schema, method)
        if (hit := self._cached(key)) is not None:
            return hit
        if self.stopped:
            raise Exhausted(f"{self.name}: stopped for this run ({self.stopped})")
        # C4 single-flight: the same request at the same moment (two threads, or the API and a CLI) is sent once;
        # the others wait here, then find the reply in the cache
        with shared_files.flight(self.cache_file.parent, key):
            if (hit := self._cached(key)) is not None:
                return hit
            return self._send(key, messages, tools, schema, method)

    def _refresh(self) -> None:
        self._shared.refresh()

    def _answered_recently(self) -> bool:
        t = _LAST_OK.get(self.name)
        return t is not None and time.monotonic() - t <= RECENT_OK_S

    def _cached(self, key: str) -> Reply | None:
        if key not in self.cache:
            self._refresh()
        if key in self.cache:
            self.hits += 1
            return self._reply(self.cache[key], cached=True)
        return None

    def _send(self, key: str, messages: list[BaseMessage], tools, schema: type[BaseModel] | None,
              method: str | None) -> Reply:
        self.quota.check(self.provider, self.model)

        if self._chat is None:
            self._chat = chat_model(self.provider, self.model, **self.params)
        runnable = cast(Any, self._chat)
        if tools:
            runnable = runnable.bind_tools(tools)
        if schema:
            runnable = runnable.with_structured_output(schema, method=method, include_raw=True)
        est = sum(est_tokens(message_text(m)) for m in messages) + OUTPUT_RESERVE_TOKENS
        if tools:
            est += est_tokens(json.dumps([convert_to_openai_tool(t) for t in tools]))
        est = min(est, self.budget.tpm)  # a larger estimate would wait forever; the provider decides

        for attempt in range(2):
            self.quota.reserve(self.provider, self.model)        # C1: the day's slot, before sending (every attempt)
            self.budget.wait(est)
            t0 = time.perf_counter()
            try:
                out = runnable.invoke(messages)
            except Exception as e:  # noqa: BLE001 — classified below, never swallowed silently
                self.budget.record(est)
                kind, wait = classify(e)
                text = redact(" | ".join(f"{type(x).__name__}: {x}" for x in _chain(e)))[:600]
                if kind == "quota_day":
                    self.quota.exhaust(self.provider, self.model, text)
                    raise Exhausted(f"{self.name}: daily quota exhausted — stopped until the provider's day ends "
                                    f"({text[:200]})") from None
                if kind in ("rate_minute", "transient") and attempt == 0 and (wait or 0) <= MAX_RATE_WAIT_S:
                    # a per-minute limit clears with a full window (Groq's output-tokens-per-minute limit came back
                    # after a 20 s wait); a transient server error gets a short wait
                    pause = max(wait or 0.0, MAX_RATE_WAIT_S) if kind == "rate_minute" else (wait or 20.0)
                    print(f"   {self.name}: {kind}, one retry in {pause:.0f} s ({text[:160]})", flush=True)
                    time.sleep(pause)
                    continue
                if kind in ("bad_request", "model_missing", "too_large"):
                    return self._store(key, None, {"kind": kind, "text": text}, None)
                if kind == "transient" and self._answered_recently() and \
                        self.quota.server_failure(key, self.name, text) >= REPEATED_SERVER_RUNS:
                    # the same request failed in separate runs, each after its retry, while the model answered other
                    # requests: a property of the request (e.g. gemma on a long tool result), not an outage — cached,
                    # so the item scores as failed. During an outage (no answer here lately) nothing is counted (M7).
                    return self._store(key, None, {"kind": "server_error_repeated", "text": text}, None)
                self.stopped = f"{kind}: {text[:200]}"
                raise Exhausted(f"{self.name}: {self.stopped}") from None
            ms = (time.perf_counter() - t0) * 1000
            o = cast(Any, out)
            msg = o["raw"] if schema else o
            usage = dict(msg.usage_metadata) if getattr(msg, "usage_metadata", None) else None
            self.budget.record((usage or {}).get("total_tokens", est))
            self.calls += 1
            _LAST_OK[self.name] = time.monotonic()
            if (usd := cost_usd(self.provider, self.model, usage)) > 0:
                self.quota.add_spend(self.provider, self.model, usd)
            return self._store(key, msg, None, ms, usage)
        raise AssertionError("unreachable")

    def _store(self, key: str, msg: AIMessage | None, error: dict | None, ms: float | None,
               usage: dict | None = None) -> Reply:
        rec = {"key": key, "model": self.name, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "latency_ms": round(ms, 1) if ms is not None else None, "usage": usage,
               "message": message_to_dict(msg) if msg is not None else None, "error": error}
        shared_files.append_line(self.cache_file, json.dumps(rec, ensure_ascii=False, default=str))   # C3
        self.cache[key] = json.loads(json.dumps(rec, default=str))
        return self._reply(self.cache[key], cached=False)

    @staticmethod
    def _reply(rec: dict, cached: bool) -> Reply:
        msg = messages_from_dict([rec["message"]])[0] if rec.get("message") else None
        return Reply(rec["key"], cast(Any, msg), rec.get("error"), cached, rec.get("latency_ms"), rec.get("usage"))


def parse_structured(reply: Reply, schema: type[BaseModel]) -> tuple[BaseModel | None, str | None]:
    """The reply as a validated `schema` instance, or the reason it is not one. Tool-call arguments when the model
    answered with a tool call (function_calling), else the text as JSON (json_schema / json_mode; code fences
    tolerated)."""
    if not reply.ok:
        return None, f"no reply: {reply.error}"
    m = cast(Any, reply.message)                           # reply.ok: the message is set
    try:
        if m.tool_calls:
            data = m.tool_calls[0]["args"]
        else:
            text = message_text(m).strip()
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
            data = json.loads(text)
        return schema.model_validate(data), None
    except Exception as e:  # noqa: BLE001 — the reason is the measurement
        return None, f"{type(e).__name__}: {str(e)[:300]}"
