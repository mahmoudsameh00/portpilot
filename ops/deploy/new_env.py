"""Write a new environment's env file with fresh credentials (Staging readiness plan P4 / P8, ADR-071).

Command (from the project root; standard library only):
    python ops/deploy/new_env.py staging [--site staging.example.com] [--tls owner@example.com] [--rehearsal]
        → deploy/env/staging.env (refuses to overwrite), every store password and the Qdrant key random (32 bytes,
          URL-safe), the login NAMES the same as the owner's (the restored grants name them), the external API keys
          and the scheduled identities copied from the owner's .env only with --copy-keys (else empty to fill).
    --rehearsal  the local staging rehearsal on Docker Desktop: site `localhost`, Caddy's internal CA, ports
                 127.0.0.1:8080 / 127.0.0.1:8443, Qdrant on 127.0.0.1:16333, stack portpilot-rehearsal.

Why fresh values: the owner's old database password is in the git history (pre-ADR-015 notebooks) and every
environment must have its own secrets; `Backup.py secure` applies these passwords after a restore.
Writes:  deploy/env/<name>.env only (mode 600 where the OS supports it). Prints no secret.
"""
import argparse
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "deploy" / "env.example"
RANDOM = ("PGPASSWORD", "PG_RO_PASSWORD", "PG_BI_PASSWORD", "PG_AGENT_PASSWORD", "PG_API_PASSWORD",
          "MONGO_ROOT_PASSWORD", "MONGO_APP_PASSWORD", "MONGO_RO_PASSWORD", "QDRANT_API_KEY")
NAMES = ("PG_RO_USER", "PG_BI_USER", "PG_AGENT_USER", "PG_API_USER", "MONGO_ROOT_USER", "MONGO_APP_USER",
         "MONGO_RO_USER")
KEYS = ("GEMINI_API_KEY", "JINA_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "TAVILY_API_KEY", "LANGSMITH_API_KEY",
        "LANGSMITH_ENDPOINT", "SENTRY_DSN", "PACK_RUN_AS", "WATCH_RUN_AS")


def read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                v = v.strip()
                if not v.startswith(("'", '"')) and " #" in v:
                    v = v.split(" #", 1)[0].strip()
                out[k.strip()] = v.strip('"').strip("'")
    return out


def shown(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("env", choices=["staging", "production"])
    ap.add_argument("--site", default="")
    ap.add_argument("--tls", default="", help="an email for Let's Encrypt, or `internal`")
    ap.add_argument("--rehearsal", action="store_true")
    ap.add_argument("--copy-keys", action="store_true", help="copy the external API keys / identities from .env")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    local = read_env(ROOT / ".env")
    values: dict[str, str] = {k: secrets.token_urlsafe(32) for k in RANDOM}
    values["MONGO_ROOT_USER"] = "portpilot_root"
    for k in NAMES:
        if k != "MONGO_ROOT_USER":
            values[k] = local.get(k, "") or k.lower().replace("_user", "")
    if a.copy_keys:
        values.update({k: local.get(k, "") for k in KEYS})
    values["PORTPILOT_ENV"] = a.env
    if a.rehearsal:
        values.update(PORTPILOT_STACK="portpilot-rehearsal", PORTPILOT_SITE="localhost",
                      PORTPILOT_WEB_ORIGIN="https://localhost:8443", CADDY_TLS="internal",
                      PROXY_HTTP_BIND="127.0.0.1:8080", PROXY_HTTPS_BIND="127.0.0.1:8443",
                      QDRANT_HOST_PORT="16333", QDRANT_HOST_URL="http://127.0.0.1:16333")
    else:
        if not (a.site and a.tls):
            sys.exit("--site and --tls are needed for a real environment (or --rehearsal)")
        values.update(PORTPILOT_STACK=f"portpilot-{a.env}", PORTPILOT_SITE=a.site,
                      PORTPILOT_WEB_ORIGIN=f"https://{a.site}", CADDY_TLS=a.tls)
    out = a.out or ROOT / "deploy" / "env" / (f"{a.env}-rehearsal.env" if a.rehearsal else f"{a.env}.env")
    if out.exists():
        sys.exit(f"{shown(out)} exists: nothing written (delete it first to start over)")
    lines = []
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key and key in values:
            lines.append(f"{key}={values[key]}")          # no inline comment: every parser reads the same value
        else:
            lines.append(line)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    try:
        os.chmod(out, 0o600)
    except OSError:
        pass
    empty = [k for k in KEYS if not values.get(k)]
    print(f"wrote {shown(out)}: {len(RANDOM)} fresh secrets"
          + (f"; fill these before starting: {', '.join(empty)}" if empty else ""))


if __name__ == "__main__":
    main()
