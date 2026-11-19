"""The models file `pipelines/agents/models.toml` (Model flexibility plan §2a): loaded once, validated, one view.

- `providers()` / `models()` / `roles()` are the current configuration of this process. They come from the tracked
  file; only an evaluation script may switch them to another file (`use(path)`, plan decision M4 — `EVAL_MODELS`).
- `model_for(provider, model_id)` finds the entry of a model the roles use; a model without an entry (a bake-off
  candidate, a check's stub provider) falls back to its provider's defaults in `llm.py`.
- Validation happens at load: an unknown provider, adapter or structured-output method, a role naming a model that
  is not in the file, an empty role, malformed limits or prices → one `ModelConfigError` naming the entry, at start-up
  rather than in the middle of a pack. Whether a key is in `.env` is checked when the real roles are built
  (`roles.Roles`), because `.env` is loaded there.
- Separate from `llm.py` and `roles.py` so both can read it without an import cycle.
"""
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from pipelines.lib.common import project_root

DEFAULT_FILE = Path(__file__).with_name("models.toml")
ADAPTERS = ("gemini", "groq", "openai_compatible", "langchain")
METHODS = ("function_calling", "json_schema", "json_mode")
SCOPES = ("model", "provider")
LIMIT_KEYS = {"rpm", "tpm", "rpd", "scope"}
MODEL_KEYS = {"provider", "id", "structured", "temperature", "timeout_s", "limits", "price_usd_per_mtok",
              "max_usd_per_day"}
PROVIDER_KEYS = {"adapter", "key_env", "base_url", "lc_provider", "day_tz", "limits", "candidates"}


class ModelConfigError(ValueError):
    """The models file is wrong; the message names the entry."""


@dataclass(frozen=True)
class ModelEntry:
    name: str                                   # the entry name in the file, e.g. "flash_lite"
    provider: str
    id: str
    structured: str
    temperature: float | None                   # None = not sent (W4)
    timeout_s: float
    limits: dict                                # rpm, tpm, rpd (None = no local daily stop), scope
    price_in: float | None = None               # USD per million input tokens (paid models)
    price_out: float | None = None
    max_usd_per_day: float | None = None


@dataclass
class Config:
    path: Path
    providers: dict[str, dict]
    models: dict[str, ModelEntry]
    roles: dict[str, tuple[str, ...]]
    by_id: dict[tuple[str, str], ModelEntry] = field(default_factory=dict)


def _limits(where: str, raw, base: dict | None = None) -> dict:
    if not isinstance(raw, dict) or set(raw) - LIMIT_KEYS:
        raise ModelConfigError(f"{where}: limits must be a table of {sorted(LIMIT_KEYS)}, got {raw!r}")
    out = {**(base or {}), **raw}
    for k in ("rpm", "tpm"):
        if not isinstance(out.get(k), int) or out[k] <= 0:
            raise ModelConfigError(f"{where}: limits.{k} must be a positive integer")
    rpd = out.get("rpd")
    if rpd is not None and (not isinstance(rpd, int) or rpd <= 0):
        raise ModelConfigError(f"{where}: limits.rpd must be a positive integer or absent")
    if out.get("scope", "model") not in SCOPES:
        raise ModelConfigError(f"{where}: limits.scope must be one of {SCOPES}")
    return {"rpm": out["rpm"], "tpm": out["tpm"], "rpd": rpd, "scope": out.get("scope", "model")}


def _number(where: str, v, *, positive: bool = True) -> float:
    if isinstance(v, bool) or not isinstance(v, int | float) or (v <= 0 if positive else v < 0):
        raise ModelConfigError(f"{where} must be a {'positive' if positive else 'non-negative'} number, got {v!r}")
    return float(v)


def parse(data: dict, path: Path) -> Config:
    """The validated configuration of one parsed TOML document."""
    if set(data) - {"providers", "models", "roles"}:
        raise ModelConfigError(f"{path.name}: unknown top-level tables {sorted(set(data) - {'providers', 'models', 'roles'})}")
    providers: dict[str, dict] = {}
    for name, p in (data.get("providers") or {}).items():
        where = f"providers.{name}"
        if set(p) - PROVIDER_KEYS:
            raise ModelConfigError(f"{where}: unknown keys {sorted(set(p) - PROVIDER_KEYS)}")
        if p.get("adapter") not in ADAPTERS:
            raise ModelConfigError(f"{where}: adapter must be one of {ADAPTERS}, got {p.get('adapter')!r}")
        if not p.get("key_env"):
            raise ModelConfigError(f"{where}: key_env (the .env variable of the key) is required")
        if p["adapter"] == "openai_compatible" and not p.get("base_url"):
            raise ModelConfigError(f"{where}: the openai_compatible adapter needs base_url")
        if p["adapter"] == "langchain" and not p.get("lc_provider"):
            raise ModelConfigError(f"{where}: the langchain adapter needs lc_provider (init_chat_model's model_provider)")
        lim = _limits(where, p.get("limits") or {}) if p.get("limits") else None
        if lim is None:
            raise ModelConfigError(f"{where}: limits (the defaults of the provider's models) are required")
        providers[name] = {"adapter": p["adapter"], "key": p["key_env"], "day_tz": p.get("day_tz", "UTC"),
                           **({"base_url": p["base_url"]} if p.get("base_url") else {}),
                           **({"lc_provider": p["lc_provider"]} if p.get("lc_provider") else {}),
                           **lim, "candidates": list(p.get("candidates") or [])}
    models: dict[str, ModelEntry] = {}
    by_id: dict[tuple[str, str], ModelEntry] = {}
    for name, m in (data.get("models") or {}).items():
        where = f"models.{name}"
        if set(m) - MODEL_KEYS:
            raise ModelConfigError(f"{where}: unknown keys {sorted(set(m) - MODEL_KEYS)}")
        if m.get("provider") not in providers:
            raise ModelConfigError(f"{where}: provider {m.get('provider')!r} is not a [providers.x] block")
        if not m.get("id"):
            raise ModelConfigError(f"{where}: id (the provider's model id) is required")
        if m.get("structured") not in METHODS:
            raise ModelConfigError(f"{where}: structured must be one of {METHODS}, got {m.get('structured')!r}")
        base = {k: providers[m["provider"]][k] for k in ("rpm", "tpm", "rpd", "scope")}
        limits = _limits(where, m["limits"], base) if "limits" in m else base
        price = m.get("price_usd_per_mtok")
        if price is not None and (not isinstance(price, dict) or set(price) != {"input", "output"}):
            raise ModelConfigError(f"{where}: price_usd_per_mtok must be {{ input = …, output = … }}")
        cap = m.get("max_usd_per_day")
        if cap is not None and price is None:
            raise ModelConfigError(f"{where}: max_usd_per_day needs price_usd_per_mtok (a cap on an unknown price)")
        e = ModelEntry(name, m["provider"], m["id"], m["structured"],
                       None if m.get("temperature") is None else _number(f"{where}.temperature", m["temperature"],
                                                                         positive=False),
                       _number(f"{where}.timeout_s", m.get("timeout_s", 120)), limits,
                       _number(f"{where}.price.input", price["input"], positive=False) if price else None,
                       _number(f"{where}.price.output", price["output"], positive=False) if price else None,
                       _number(f"{where}.max_usd_per_day", cap) if cap is not None else None)
        if (e.provider, e.id) in by_id:
            raise ModelConfigError(f"{where}: {e.provider}/{e.id} already has the entry {by_id[e.provider, e.id].name}")
        models[name], by_id[e.provider, e.id] = e, e
    roles: dict[str, tuple[str, ...]] = {}
    for role, names in (data.get("roles") or {}).items():
        if not isinstance(names, list) or not names:
            raise ModelConfigError(f"roles.{role}: a non-empty list of model entries, main first")
        missing = [n for n in names if n not in models]
        if missing:
            raise ModelConfigError(f"roles.{role}: {missing} not in [models]")
        if len(set(names)) != len(names):
            raise ModelConfigError(f"roles.{role}: a model listed twice")
        roles[role] = tuple(names)
    if not roles:
        raise ModelConfigError(f"{path.name}: [roles] is empty")
    return Config(path, providers, models, roles, by_id)


def load(path: Path | str | None = None) -> Config:
    p = Path(path) if path else DEFAULT_FILE
    if not p.is_absolute():
        p = project_root() / p
    try:
        data = tomllib.loads(p.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ModelConfigError(f"{p}: {e}") from None
    return parse(data, p)


_CURRENT = load()


def current() -> Config:
    return _CURRENT


def use(path: Path | str | None) -> Config:
    """Switch this process to another models file (evaluation scripts only, EVAL_MODELS — M4); None = the tracked
    file. The caller rebuilds what it derived (`roles.reload()` does it for the roles and `llm.PROVIDERS`)."""
    global _CURRENT
    _CURRENT = load(path)
    return _CURRENT


def eval_file() -> str | None:
    """The EVAL_MODELS file an evaluation script was asked to use, if any."""
    return os.environ.get("EVAL_MODELS") or None


def model_for(provider: str, model_id: str) -> ModelEntry | None:
    return _CURRENT.by_id.get((provider, model_id))
