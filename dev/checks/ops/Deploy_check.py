"""Staging readiness plan (ADR-071): the deployment's rules, checked without a database, a network or Docker — in the
CI and on the owner's machine.

Run: uv run python dev/tools/run.py dev/checks/ops/Deploy_check.py
Reads: code and the deploy files only. Writes: temporary folders, removed at the end. No database, network or model.
Re-run: safe. Final Checkpoint: dev/checkpoints/ops/Deploy_check.md.
"""
# %% Setup
import hashlib
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import yaml

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from pipelines.lib import common, environment  # noqa: E402


def load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def env(**values):
    """Patch os.environ for one block (None = unset)."""
    clean = {k: v for k, v in values.items() if v is not None}
    drop = [k for k, v in values.items() if v is None]
    p = patch.dict(os.environ, clean)
    p.start()
    for k in drop:
        os.environ.pop(k, None)
    return p


# %% Phase 1 — The environment name and what it changes (P1)
p = env(PORTPILOT_ENV=None)
assert environment.name() == "local" and environment.bind_host() == "127.0.0.1" and environment.docs_enabled()
environment.require_local("test")                                    # local: allowed
p.stop()
for bad in ("prod", "Staging2", "dev"):
    p = env(PORTPILOT_ENV=bad)
    try:
        environment.name()
        raise AssertionError(f"{bad} accepted")
    except RuntimeError:
        pass
    p.stop()
for name in ("staging", "production"):
    p = env(PORTPILOT_ENV=name, API_BIND_HOST="0.0.0.0")
    assert environment.bind_host() == "0.0.0.0"
    assert environment.docs_enabled() == (name == "staging")
    try:
        environment.require_local("--fake-roles")
        raise AssertionError("a test mode ran outside local")
    except SystemExit as e:
        assert "refused" in str(e)
    p.stop()
p = env(PORTPILOT_ENV="local", API_BIND_HOST="0.0.0.0")
assert environment.bind_host() == "127.0.0.1", "locally the bind is always the loopback"
p.stop()
# `.env` optional outside local, still required locally
with tempfile.TemporaryDirectory() as tmp:
    (Path(tmp) / "pyproject.toml").write_text("", encoding="utf-8")
    (Path(tmp) / "Data").mkdir()
    p = env(PORTPILOT_ENV="staging")
    common.load_env(Path(tmp))                                       # no .env: no error
    p.stop()
    p = env(PORTPILOT_ENV=None)
    try:
        common.load_env(Path(tmp))
        raise AssertionError("a missing .env passed locally")
    except FileNotFoundError:
        pass
    p.stop()
# Serve.py refuses the fake model outside local, even with API_FAKE_ROLES=1
r = subprocess.run([sys.executable, "pipelines/scripts/api/Serve.py", "--fake-roles"], cwd=ROOT, capture_output=True,
                   text=True, timeout=120, env={**os.environ, "PORTPILOT_ENV": "staging", "API_FAKE_ROLES": "1",
                                                "SENTRY_DSN": ""})
assert r.returncode != 0 and "refused in PORTPILOT_ENV=staging" in (r.stderr + r.stdout), (r.returncode, r.stderr[-300:])
from pipelines.api import config, fake  # noqa: E402
p = env(PORTPILOT_ENV="production")
try:
    fake.create_fake_app()
    raise AssertionError("the fake app was built in production")
except SystemExit:
    pass
p.stop()
# CORS: https only outside local
p = env(PORTPILOT_ENV="staging", API_CORS_ORIGINS="http://staging.example.com")
try:
    config.cors_origins()
    raise AssertionError("an http origin passed in staging")
except ValueError:
    pass
p.stop()
p = env(PORTPILOT_ENV="staging", API_CORS_ORIGINS="https://staging.example.com")
assert config.cors_origins() == ["https://staging.example.com"]
p.stop()
# the docs pages off in production, the open status route present
from pipelines.api.app import create_app  # noqa: E402
p = env(PORTPILOT_ENV="production", API_CORS_ORIGINS="https://portpilot.example.com")
from fastapi.testclient import TestClient  # noqa: E402
app = create_app(access_log=None)
client = TestClient(app)                     # no `with`: the lifespan (run executor) is not started
assert client.get("/docs").status_code == 404 and client.get("/redoc").status_code == 404
assert client.get("/api/v1/health/live").json() == {"status": "live"}
assert "/api/v1/health/status" in app.openapi()["paths"]
p.stop()
p = env(PORTPILOT_ENV="staging", API_CORS_ORIGINS="https://staging.example.com")
assert TestClient(create_app(access_log=None)).get("/docs").status_code == 200     # staging keeps the docs page
p.stop()
assert "PG_API_PASSWORD" in common.SECRET_KEYS and "SENTRY_DSN" in common.SECRET_KEYS
print("✅ Phase 1 validation passed: PORTPILOT_ENV local / staging / production (an unknown name stops); the bind "
      "is the loopback locally and API_BIND_HOST outside; .env optional only outside local; --fake-roles and the fake "
      "app refused in staging / production; CORS https-only outside local; /docs off in production, /health/status "
      "open; redact() knows PG_API_PASSWORD")

# %% Phase 2 — The compose stack's exposure and least privilege (P4)
compose = yaml.safe_load((ROOT / "deploy" / "compose.yaml").read_text(encoding="utf-8"))
svc = compose["services"]
assert set(svc) == {"postgres", "mongo", "qdrant", "api", "scheduler", "web", "proxy", "ops"}, sorted(svc)
published = {n: s.get("ports", []) for n, s in svc.items() if s.get("ports")}
assert set(published) == {"proxy", "qdrant"}, published
assert all(str(x).startswith("127.0.0.1:") for x in published["qdrant"]), "Qdrant only on the host loopback"
assert compose["networks"]["backend"].get("internal") is True
for n in ("postgres", "mongo", "qdrant", "api", "scheduler", "web", "ops"):
    assert "frontend" not in svc[n].get("networks", []) or n == "web", f"{n} on the public network"
assert "backend" not in svc["proxy"]["networks"], "the proxy reaches the web only"
assert not any("env_file" in s for s in svc.values()), "no env_file: each service lists its variables"
for n in ("api", "scheduler", "web", "ops"):
    s = svc[n]
    assert s.get("read_only") is True and s.get("cap_drop") == ["ALL"], n
    assert "no-new-privileges:true" in s.get("security_opt", []), n
for n, s in svc.items():
    image = s["image"]
    assert ":" in image and not image.endswith(":latest"), f"{n}: unpinned image {image}"
    envs = s.get("environment", {}) or {}
    holds_owner = "PGPASSWORD" in envs or "POSTGRES_PASSWORD" in envs
    assert holds_owner == (n in ("postgres", "ops")), f"{n}: the database owner's password"
web_env = set(svc["web"]["environment"])
assert web_env == {"PORTPILOT_API_URL", "PORTPILOT_WEB_ORIGIN", "PORTPILOT_TRUST_PROXY"}, web_env
assert svc["web"]["environment"]["PORTPILOT_TRUST_PROXY"] == "1"
for n in ("postgres", "mongo", "qdrant"):
    keys = " ".join(map(str, (svc[n].get("environment") or {}).keys()))
    assert not re.search(r"GEMINI|GROQ|OPENROUTER|JINA|TAVILY|LANGSMITH|SENTRY", keys), f"{n} sees a model key"
assert svc["api"]["environment"]["API_BIND_HOST"] == "0.0.0.0" and svc["api"]["environment"]["PORTPILOT_ENV"]
assert svc["ops"].get("profiles") == ["ops"]
assert svc["scheduler"]["command"][-1].endswith("Scheduler_service.py")
assert all(s.get("logging") for n, s in svc.items()), "log rotation on every service"
required = set(re.findall(r"\$\{([A-Z_]+):\?", (ROOT / "deploy" / "compose.yaml").read_text(encoding="utf-8")))
example = {ln.split("=", 1)[0].strip() for ln in (ROOT / "deploy" / "env.example").read_text(encoding="utf-8")
           .splitlines() if "=" in ln and not ln.lstrip().startswith("#")}
assert required <= example, f"required by compose, missing from env.example: {sorted(required - example)}"
caddy = (ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")
assert "respond @api 404" in caddy and "Strict-Transport-Security" in caddy and "max_size 6MB" in caddy
assert "admin off" in caddy and "reverse_proxy web:3000" in caddy
print(f"✅ Phase 2 validation passed: {len(svc)} services; only the proxy (and Qdrant on the host loopback) publish "
      "a port; the stores on the internal network; no env_file, the database owner's password only in postgres / ops, "
      "no model key in a store, the web holds no secret; read-only roots, all capabilities dropped, pinned images, "
      f"log rotation; the {len(required)} required variables are in env.example; Caddy hides the API, sets HSTS and a "
      "body limit")

# %% Phase 3 — The image (P3)
dockerfile = (ROOT / "ops" / "docker" / "api.Dockerfile").read_text(encoding="utf-8")
ignore = [ln.strip() for ln in (ROOT / "ops" / "docker" / "api.Dockerfile.dockerignore").read_text(encoding="utf-8")
          .splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
assert re.search(r"^USER portpilot$", dockerfile, re.M) and "python:3.13.5-slim" in dockerfile
assert "--frozen" in dockerfile and "--no-dev" in dockerfile and "apt-get" not in dockerfile
assert ignore[0] == "*" and "!Data/" in ignore and "Data/raw/" in ignore and "**/.env" in ignore
assert all(x in ignore for x in ("Data/processed/agents/eval/llm_cache/", "Data/embeddings/"))
web_docker = (ROOT / "web" / "Dockerfile").read_text(encoding="utf-8")
assert "USER node" in web_docker
print("✅ Phase 3 validation passed: the API image runs as `portpilot`, from the locked runtime packages only, no apt; "
      "its context lets in no .env, raw data, cache or model; the web image runs as `node`")

# %% Phase 4 — The scheduler service (P5)
sched = load("pipelines/scripts/ops/Scheduler_service.py", "sched")
cairo = ZoneInfo("Africa/Cairo")
pack, watch = sched.JOBS
mon = datetime(2026, 11, 16, 10, 30, tzinfo=cairo)                   # a Monday
assert mon.weekday() == 0
assert sched.last_due(pack, mon + timedelta(minutes=1)) == mon
assert sched.last_due(pack, mon - timedelta(minutes=1)) == mon - timedelta(days=7)
assert sched.next_due(watch, mon) == mon.replace(hour=22)
assert sched.decide(pack, None, mon + timedelta(hours=1))[0] == "init"            # first start: nothing fires
assert sched.decide(pack, mon - timedelta(days=7), mon + timedelta(hours=1)) == ("fire", mon)
assert sched.decide(pack, mon - timedelta(days=7), mon + timedelta(hours=13))[0] == "skip"   # past the 12 h catch-up
assert sched.decide(pack, mon, mon + timedelta(days=2))[0] == "wait"
assert sched.decide(watch, mon, mon + timedelta(hours=12, minutes=5)) == ("fire", mon.replace(hour=22, minute=30))
summer = datetime(2026, 7, 6, 10, 30, tzinfo=cairo)                  # Egypt's summer time (UTC+3)
assert sched.last_due(pack, summer).utcoffset() == timedelta(hours=3)
with tempfile.TemporaryDirectory() as tmp:
    for attr, value in (("LOG_DIR", Path(tmp)), ("STATE", Path(tmp) / "s.json"), ("JOURNAL", Path(tmp) / "j.jsonl")):
        setattr(sched, attr, value)              # the service's files into a temporary folder
    fired: list[str] = []
    state = sched.tick(mon + timedelta(minutes=5), {}, runner=lambda j, d: fired.append(j.name))
    assert not fired and set(state) == {"weekly_pack", "voyage_watch"}
    state = sched.tick(mon + timedelta(days=7, minutes=5), sched.load_state(), runner=lambda j, d: fired.append(j.name))
    assert fired == ["weekly_pack", "voyage_watch"], fired                      # Monday 10:30: both jobs, in order
    assert sched.load_state()["weekly_pack"] == mon + timedelta(days=7)
print("✅ Phase 4 validation passed: Monday 10:30 and daily 10:30 / 22:30 Africa/Cairo (summer time included); the "
      "first start fires nothing; a missed firing runs once inside its catch-up window and is skipped after it; one "
      "job at a time; the state survives a restart")

# %% Phase 5 — Migrations on deploy (P7)
mig = load("pipelines/scripts/ops/Migrate.py", "mig")
fs = mig.files()
assert sorted(fs) == list(range(1, max(fs) + 1)) and max(fs) >= 31
rows = re.findall(r"\((\d+),\s+'(\d{3}_[a-z0-9_]+\.sql)',\s+'([0-9a-f]{64})'",
                  (ROOT / "db" / "migrations" / "031_schema_migrations.sql").read_text(encoding="utf-8"))
assert len(rows) == 30, len(rows)
for v, f, h in rows:
    assert fs[int(v)].name == f and mig.text_hash(fs[int(v)]) == h, f"031 records a different text for {f}"
crlf = hashlib.sha256(b"SELECT 1;\n").hexdigest()
with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp) / "x.sql"
    t.write_bytes(b"SELECT 1;\r\n")
    assert mig.text_hash(t) == crlf, "CRLF and LF checkouts must hash the same"
print(f"✅ Phase 5 validation passed: {len(fs)} migrations numbered without a gap; 031 records 001–030 with the "
      "hash of each file's current text (CRLF read as LF)")

# %% Phase 6 — Backups: env parsing, retention, fresh environments (P6 / P8)
bk = load("pipelines/scripts/ops/Backup.py", "bk")
with tempfile.TemporaryDirectory() as tmp:
    f = Path(tmp) / "e.env"
    f.write_text("A=1\nB=two   # a comment\nC='x # y'\n# D=no\n", encoding="utf-8")
    assert bk.read_env(f) == {"A": "1", "B": "two", "C": "x # y"}
    out = Path(tmp) / "b"
    stamps = [datetime(2026, 11, 17) - timedelta(days=i) for i in range(40)]
    for s in stamps:
        d = out / f"portpilot-x_{s:%Y%m%dT%H%M%SZ}"
        d.mkdir(parents=True)
        (d / "manifest.json").write_text("{}", encoding="utf-8")
    bk.cmd_prune(out, 7, 4, dry_run=False)
    left = sorted(p.name for p in out.iterdir())
    # the 7 newest days (11-11 … 11-17) + the newest of each of the 4 newest ISO weeks (11-17, 11-15 already kept;
    # 11-08, 11-01 added) = 9
    assert len(left) == 9, left
    newenv = load("ops/deploy/new_env.py", "newenv")
    target = Path(tmp) / "r.env"
    with patch.object(sys, "argv", ["new_env.py", "staging", "--rehearsal", "--out", str(target)]):
        newenv.main()
    vals = bk.read_env(target)
    secrets_ = [vals[k] for k in newenv.RANDOM]
    assert all(len(v) >= 40 for v in secrets_) and len(set(secrets_)) == len(secrets_)
    local = newenv.read_env(ROOT / ".env") if (ROOT / ".env").exists() else {}
    assert not (set(secrets_) & set(local.values())), "a fresh environment reused a local secret"
    assert vals["PORTPILOT_ENV"] == "staging" and vals["CADDY_TLS"] == "internal"
    assert vals["PORTPILOT_WEB_ORIGIN"] == "https://localhost:8443" and vals["QDRANT_HOST_URL"].startswith("http://127.")
print("✅ Phase 6 validation passed: env files read the same everywhere (inline comments, quotes); retention keeps 7 "
      "daily + 4 weekly; a new environment gets 9 fresh secrets, all different and none from the owner's .env")

# %% Final Checkpoint
print("✅ Final Checkpoint: Deploy_check Phases 1–6 passed (no database, no network, no Docker)")
