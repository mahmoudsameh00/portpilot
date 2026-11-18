"""Scan the working tree for secrets (Staging readiness plan P8, e4; ADR-071). No git: it reads files, so it sees
what a checkout holds today; the git HISTORY is scanned by the owner with gitleaks (docs/deploy/RUNBOOK.md §Secrets).

    uv run python tools/secrets_scan.py            exit 0 = nothing found, 1 = findings (file:line and the rule; the
                                                   matched value is never printed, only its first 4 characters)

Two rules:
1. **Known values.** Every secret of the owner's `.env` and of `deploy/env/*.env` (the keys of
   `pipelines.lib.common.SECRET_KEYS` + every `*PASSWORD*` / `*_KEY` / `*DSN*`, 8+ characters) must appear in no
   other file.
2. **Key shapes.** Provider key formats (Google, Groq, OpenRouter, LangSmith, Tavily, Jina, GitHub, AWS, Slack,
   Azure storage), Sentry DSNs with a key, private-key blocks and connection strings with an inline password.
Skipped: ignored folders (.git, .venv, node_modules, Data/raw, models, backups, reports, caches, build output),
the env files themselves, files over 5 MB and binary files. A line may opt out with `secrets-scan: allow` when it
holds a documented fake (a test fixture).
"""
import re
import sys
from pathlib import Path

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from pipelines.lib.common import SECRET_KEYS  # noqa: E402

SKIP_DIRS = {".git", ".venv", "node_modules", ".next", "__pycache__", ".ruff_cache", "graphify-out", "backups",
             "reports", "models", "playwright-report", "test-results", "_scratch", ".pytest_cache"}
SKIP_PATHS = ("Data/raw/", "Data/processed/agents/eval/llm_cache/", "Data/processed/agents/tool_cache/",
              "Data/embeddings/", "Data/incoming/", "deploy/env/")
ENV_FILES = (".env", ".env.local", "web/.env.local")
MAX_BYTES = 5 * 1024 * 1024
ALLOW = "secrets-scan: allow"
SHAPES = {
    "google_api_key": r"AIza[0-9A-Za-z_\-]{35}",
    "groq_key": r"gsk_[A-Za-z0-9]{40,}",
    "openrouter_key": r"sk-or-v1-[0-9a-f]{48,}",
    "openai_style_key": r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}",
    "langsmith_key": r"lsv2_(?:pt|sk)_[0-9a-f]{32}_[0-9a-f]{8,}",
    "tavily_key": r"tvly-[A-Za-z0-9\-]{24,}",
    "jina_key": r"jina_[A-Za-z0-9]{40,}",
    "github_token": r"\bgh[pousr]_[A-Za-z0-9]{36,}",
    "aws_access_key": r"\bAKIA[0-9A-Z]{16}\b",
    "slack_token": r"xox[baprs]-[A-Za-z0-9-]{10,}",
    "azure_storage_key": r"AccountKey=[A-Za-z0-9+/=]{40,}",
    "sentry_dsn": r"https://[0-9a-f]{32}@o\d+\.ingest\.(?:[a-z]+\.)?sentry\.io/\d+",
    "private_key": r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----",
    "url_password": r"\b(?:postgres(?:ql)?|mongodb(?:\+srv)?|redis|amqp)://[^:/\s'\"]+:[^@/\s'\"$<{]{6,}@",
}
COMPILED = {k: re.compile(v) for k, v in SHAPES.items()}
# a value that is an ordinary word is not searched (it would match every mention of the word) but reported as WEAK:
# such a password must be rotated before anything leaves the loopback (runbook §Rotation)
TRIVIAL = {"postgres", "password", "changeme", "secret12", "administrator", "portpilot", "nilegate", "12345678"}


def env_secrets() -> dict[str, str]:
    files = [ROOT / f for f in ENV_FILES] + sorted((ROOT / "deploy" / "env").glob("*.env"))
    out: dict[str, str] = {}
    for f in files:
        if not f.is_file():
            continue
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.split(" #", 1)[0].strip().strip('"').strip("'")
            secret = k in SECRET_KEYS or "PASSWORD" in k or k.endswith("_KEY") or "DSN" in k
            if secret and len(v) >= 8:
                out[v] = f"{f.relative_to(ROOT).as_posix()}:{k}"
    return out


def candidates():
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts) or rel.startswith(SKIP_PATHS):
            continue
        if rel in ENV_FILES or rel.endswith((".env",)) and rel != ".env.example":
            continue
        try:
            if p.stat().st_size > MAX_BYTES:
                continue
            data = p.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:4096]:
            continue
        yield rel, data.decode("utf-8", errors="replace")


def main() -> None:
    known = env_secrets()
    weak = sorted(w for v, w in known.items() if v.lower() in TRIVIAL)
    known = {v: w for v, w in known.items() if v.lower() not in TRIVIAL}
    for w in weak:
        print(f"⚠️  WEAK: {w} is a dictionary word — rotate it (docs/deploy/RUNBOOK.md §Rotation); not searched")
    findings: list[str] = []
    scanned = 0
    for rel, text in candidates():
        scanned += 1
        for n, line in enumerate(text.splitlines(), 1):
            if ALLOW in line:
                continue
            for value, where in known.items():
                if value in line:
                    findings.append(f"{rel}:{n}: the value of {where} ({value[:4]}…)")
            for rule, rx in COMPILED.items():
                m = rx.search(line)
                if m:
                    findings.append(f"{rel}:{n}: {rule} ({m.group(0)[:4]}…)")
    for f in findings[:50]:
        print(f"❌ {f}")
    if findings:
        print(f"❌ secrets scan: {len(findings)} finding(s) in {scanned} files")
        sys.exit(1)
    print(f"✅ secrets scan: {scanned} files, {len(known)} known secret values and {len(SHAPES)} key shapes, "
          "0 findings")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    main()
