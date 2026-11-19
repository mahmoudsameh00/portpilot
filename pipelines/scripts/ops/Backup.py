"""Backups, restore and the restore drill of the three stores and the durable files (Staging readiness plan P6,
ADR-071). Standard library + the docker CLI only, so it runs with `uv run python` on the owner's machine and with the
system `python3` (≥ 3.11) on a deployment host.

Commands (from the project root):
    python pipelines/scripts/ops/Backup.py backup  --stack local|<prefix> [--env-file F] [--out backups] [--with-models]
    python pipelines/scripts/ops/Backup.py verify  <backup folder>
    python pipelines/scripts/ops/Backup.py restore <backup folder> --stack <prefix> --env-file F [--yes]
    python pipelines/scripts/ops/Backup.py secure  --stack <prefix> --env-file F          (after a restore: see below)
    python pipelines/scripts/ops/Backup.py prune   [--out backups] [--daily 7] [--weekly 4] [--dry-run]
    python pipelines/scripts/ops/Backup.py drill   [--keep]        the owner's local stores → fresh drill containers

Stacks. `local` = the owner's containers ports-postgres / ports-mongo / ports-qdrant (Qdrant on 127.0.0.1:6333, the
files from the working tree, credentials from `.env`). `<prefix>` = a deployment stack of deploy/compose.yaml:
containers <prefix>-postgres / -mongo / -qdrant / -api, Qdrant at QDRANT_HOST_URL of the env file (the compose file
publishes it on the host's loopback only), the files copied out of / into <prefix>-api with `docker cp`.

A backup folder `<out>/<stack>_<UTC stamp>/` holds:
    postgres/roles.sql            pg_dumpall --roles-only (password HASHES: keep the folder private)
    postgres/ports_logistics.dump pg_dump -Fc of the application database
    mongo/ports_logistics.archive.gz   mongodump --archive --gzip of the project database (users live in admin: not
                                  copied; `secure` creates them with the environment's passwords)
    qdrant/nilegate_docs.snapshot the collection snapshot (vectors, payload, indexes)
    files/runtime.tar.gz          reports/ (the published packs = durable state), the voyage file, the LLM reply cache,
                                  the tool / query caches, Data/incoming/  (+ models/onnx/bge-m3 with --with-models)
    manifest.json                 sha256 + size of each file, and the facts `verify` and the drill compare: row counts of
                                  every table, a digest of finance.kpi_weekly, MongoDB counts, Qdrant point count and a
                                  digest of (point id, text_sha256)
`restore` refuses a non-empty target unless --yes; `secure` (run after a restore into a NEW environment) sets the
runtime logins' PostgreSQL passwords from the env file, creates / updates the MongoDB app and reader users, disables
every API login and revokes every token (the owner then creates the real logins with Api_admin.py, ADR-071 / S7).

Reads:   the stores (read-only for `backup` / `verify`), the env file. Writes: only the backup folder (`backup`),
         only the target stack (`restore` / `secure`), only drill containers it creates and removes (`drill`).
Re-run:  `backup` adds a folder; `prune` deletes old folders under --out only; `drill` cleans up after itself.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
DB = "ports_logistics"
COLLECTION = "nilegate_docs"
RUNTIME_UID = 10001                       # the image's `portpilot` user (ops/docker/api.Dockerfile)
# The durable files (relative to the project root / the image's /app), ADR-071 a10
FILES = ("reports",
         "Data/processed/semi-structured/synthetic/voyages_synthetic.parquet",
         "Data/processed/agents/eval/llm_cache",
         "Data/processed/agents/tool_cache",
         "Data/embeddings/gemini-embedding-2/cache_queries",
         "Data/incoming")
# the api container's writable volumes (deploy/compose.yaml); the voyage file lives in the `synthetic` volume
VOLUME_DIRS = ("reports", "Data/processed/agents/eval/llm_cache", "Data/processed/agents/tool_cache",
               "Data/embeddings/gemini-embedding-2/cache_queries", "Data/incoming",
               "Data/processed/semi-structured/synthetic")
MODEL_FILES = ("models/onnx/bge-m3/manifest.json", "models/onnx/bge-m3/model.onnx",
               "models/onnx/bge-m3/model.onnx.data", "models/onnx/bge-m3/tokenizer.json")
RUNTIME_LOGINS = (("PG_RO_USER", "PG_RO_PASSWORD"), ("PG_BI_USER", "PG_BI_PASSWORD"),
                  ("PG_AGENT_USER", "PG_AGENT_PASSWORD"), ("PG_API_USER", "PG_API_PASSWORD"))


# ---------------------------------------------------------------- helpers
def read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            v = v.strip()
            if not v.startswith(("'", '"')) and " #" in v:      # an inline comment after an unquoted value
                v = v.split(" #", 1)[0].strip()
            out[k.strip()] = v.strip('"').strip("'")
    return out


def sh(args: list[str], *, env: dict[str, str] | None = None, stdin: bytes | None = None,
       check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a command; secrets reach `docker exec` as `-e NAME` (value from `env`), never on the command line."""
    full_env = {**os.environ, **(env or {})}
    r = subprocess.run(args, input=stdin, env=full_env, capture_output=capture, check=False)
    if check and r.returncode != 0:
        err = (r.stderr or b"").decode("utf-8", "replace")[-800:]
        raise SystemExit(f"command failed ({r.returncode}): {' '.join(args[:4])} …\n{err}")
    return r


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


class Stack:
    """Container names, the Qdrant address and the credentials of one stack."""

    def __init__(self, name: str, env_file: Path | None):
        self.name = name
        self.local = name == "local"
        self.env_file = env_file or (ROOT / ".env" if self.local else None)
        if self.env_file is None:
            raise SystemExit(f"--env-file is required for the stack {name}")
        self.env = read_env(self.env_file)
        pre = "ports" if self.local else name
        self.postgres, self.mongo, self.qdrant = f"{pre}-postgres", f"{pre}-mongo", f"{pre}-qdrant"
        self.api = None if self.local else f"{name}-api"
        self.qdrant_url = ("http://127.0.0.1:6333" if self.local
                           else self.env.get("QDRANT_HOST_URL", "").rstrip("/"))
        if not self.qdrant_url:
            raise SystemExit("QDRANT_HOST_URL (the host's loopback address of the stack's Qdrant) is missing")
        self.pg_super = self.env.get("PGUSER", "postgres") if not self.local else "postgres"

    def mongo_root(self) -> dict[str, str]:
        user = self.env.get("MONGO_ROOT_USER") or self.env.get("MONGO_INITDB_ROOT_USERNAME", "")
        pwd = self.env.get("MONGO_ROOT_PASSWORD") or self.env.get("MONGO_INITDB_ROOT_PASSWORD", "")
        if not (user and pwd):
            raise SystemExit("MONGO_ROOT_USER / MONGO_ROOT_PASSWORD missing in the env file")
        return {"NG_ROOT_USER": user, "NG_ROOT_PWD": pwd}

    def qdrant_key(self) -> str:
        key = self.env.get("QDRANT_API_KEY", "")
        if not key:
            raise SystemExit("QDRANT_API_KEY missing in the env file")
        return key


# ---------------------------------------------------------------- PostgreSQL
def psql(container: str, user: str, sql: str, db: str = DB) -> str:
    r = sh(["docker", "exec", container, "psql", "-U", user, "-d", db, "-X", "-At", "-v", "ON_ERROR_STOP=1",
            "-c", sql])
    return r.stdout.decode("utf-8").strip()


def pg_facts(container: str, user: str) -> dict:
    tables = psql(container, user,
                  "SELECT string_agg(n.nspname || '.' || c.relname, ',' ORDER BY 1) FROM pg_class c "
                  "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relkind IN ('r','p') "
                  "AND n.nspname NOT IN ('pg_catalog','information_schema','tiger','tiger_data','topology')")
    counts: dict[str, int] = {}
    names = [t for t in tables.split(",") if t]
    if names:
        sql = " UNION ALL ".join(f"SELECT '{t}', count(*) FROM {t}" for t in names)
        for line in psql(container, user, sql).splitlines():
            t, n = line.split("|")
            counts[t] = int(n)
    kpi = psql(container, user, "SELECT md5(string_agg(k::text, '|' ORDER BY k.report_week)) FROM finance.kpi_weekly k")
    return {"table_rows": counts, "kpi_weekly_md5": kpi}


def pg_backup(stack: Stack, out: Path) -> None:
    (out / "postgres").mkdir(parents=True)
    r = sh(["docker", "exec", stack.postgres, "pg_dumpall", "-U", stack.pg_super, "--roles-only"])
    (out / "postgres" / "roles.sql").write_bytes(r.stdout)
    sh(["docker", "exec", stack.postgres, "pg_dump", "-U", stack.pg_super, "-d", DB, "-Fc", "-f", "/tmp/ng_backup.dump"])
    sh(["docker", "cp", f"{stack.postgres}:/tmp/ng_backup.dump", str(out / "postgres" / f"{DB}.dump")])
    sh(["docker", "exec", stack.postgres, "rm", "-f", "/tmp/ng_backup.dump"])


def pg_restore(container: str, super_user: str, folder: Path, force: bool) -> None:
    exists = psql(container, super_user, f"SELECT count(*) FROM pg_database WHERE datname = '{DB}'", db="postgres")
    if exists == "1":
        n = psql(container, super_user, "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")
        if int(n) > 0 and not force:
            raise SystemExit(f"{container} already holds {DB} with tables: pass --yes to replace it")
        psql(container, super_user, f"DROP DATABASE {DB} WITH (FORCE)", db="postgres")
    roles = [ln for ln in (folder / "roles.sql").read_text(encoding="utf-8").splitlines()
             if not ln.startswith((f"CREATE ROLE {super_user};", f"ALTER ROLE {super_user} ",
                                   "CREATE ROLE postgres;", "ALTER ROLE postgres "))]
    sh(["docker", "exec", "-i", container, "psql", "-U", super_user, "-d", "postgres", "-X", "-q",
        "-v", "ON_ERROR_STOP=0"], stdin="\n".join(roles).encode("utf-8"))
    psql(container, super_user, f"CREATE DATABASE {DB}", db="postgres")
    sh(["docker", "cp", str(folder / f"{DB}.dump"), f"{container}:/tmp/ng_restore.dump"])
    sh(["docker", "exec", container, "pg_restore", "-U", super_user, "-d", DB, "--exit-on-error", "/tmp/ng_restore.dump"])
    sh(["docker", "exec", container, "rm", "-f", "/tmp/ng_restore.dump"])
    psql(container, super_user, "ANALYZE")


# ---------------------------------------------------------------- MongoDB
def mongosh(container: str, creds: dict[str, str], js: str) -> str:
    r = sh(["docker", "exec", "-e", "NG_ROOT_USER", "-e", "NG_ROOT_PWD", container, "sh", "-c",
            'mongosh --quiet -u "$NG_ROOT_USER" -p "$NG_ROOT_PWD" --authenticationDatabase admin --eval "$0"', js],
           env=creds)
    return r.stdout.decode("utf-8").strip()


def mongo_facts(container: str, creds: dict[str, str]) -> dict:
    js = ("const d = db.getSiblingDB('" + DB + "'); const o = {};"
          "d.getCollectionNames().filter(n => !n.startsWith('system.')).sort()"
          ".forEach(n => { o[n] = d.getCollection(n).countDocuments({}); }); print(JSON.stringify(o));")
    return {"collections": json.loads(mongosh(container, creds, js).splitlines()[-1])}


def mongo_backup(stack: Stack, out: Path) -> None:
    (out / "mongo").mkdir(parents=True)
    creds = stack.mongo_root()
    sh(["docker", "exec", "-e", "NG_ROOT_USER", "-e", "NG_ROOT_PWD", stack.mongo, "sh", "-c",
        f'mongodump --quiet -u "$NG_ROOT_USER" -p "$NG_ROOT_PWD" --authenticationDatabase admin --db {DB} '
        '--archive=/tmp/ng_backup.archive.gz --gzip'], env=creds)
    sh(["docker", "cp", f"{stack.mongo}:/tmp/ng_backup.archive.gz", str(out / "mongo" / f"{DB}.archive.gz")])
    sh(["docker", "exec", stack.mongo, "rm", "-f", "/tmp/ng_backup.archive.gz"])


def mongo_restore(container: str, creds: dict[str, str], folder: Path, force: bool) -> None:
    current = mongo_facts(container, creds)["collections"]
    if any(current.values()) and not force:
        raise SystemExit(f"{container} already holds documents in {DB}: pass --yes to replace them")
    sh(["docker", "cp", str(folder / f"{DB}.archive.gz"), f"{container}:/tmp/ng_restore.archive.gz"])
    sh(["docker", "exec", "-e", "NG_ROOT_USER", "-e", "NG_ROOT_PWD", container, "sh", "-c",
        'mongorestore --quiet -u "$NG_ROOT_USER" -p "$NG_ROOT_PWD" --authenticationDatabase admin --drop '
        f"--nsInclude '{DB}.*' --archive=/tmp/ng_restore.archive.gz --gzip"], env=creds)
    sh(["docker", "exec", container, "rm", "-f", "/tmp/ng_restore.archive.gz"])


# ---------------------------------------------------------------- Qdrant (REST)
def qdrant(url: str, key: str, method: str, path: str, body: bytes | None = None,
           ctype: str = "application/json", timeout: int = 300) -> bytes:
    req = urllib.request.Request(f"{url}{path}", data=body, method=method,
                                 headers={"api-key": key, "content-type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Qdrant {method} {path}: HTTP {e.code} {e.read()[:300]!r}") from None


def qdrant_facts(url: str, key: str) -> dict:
    info = json.loads(qdrant(url, key, "GET", f"/collections/{COLLECTION}"))["result"]
    pairs: list[str] = []
    offset = None
    while True:
        body = {"limit": 1000, "with_payload": ["text_sha256"], "with_vector": False}
        if offset is not None:
            body["offset"] = offset
        page = json.loads(qdrant(url, key, "POST", f"/collections/{COLLECTION}/points/scroll",
                                 json.dumps(body).encode()))["result"]
        pairs += [f"{p['id']}:{(p.get('payload') or {}).get('text_sha256')}" for p in page["points"]]
        offset = page.get("next_page_offset")
        if offset is None:
            break
    return {"points": info["points_count"], "ids_digest": hashlib.sha256("\n".join(sorted(pairs)).encode()).hexdigest()}


def qdrant_backup(stack: Stack, out: Path) -> None:
    (out / "qdrant").mkdir(parents=True)
    key = stack.qdrant_key()
    snap = json.loads(qdrant(stack.qdrant_url, key, "POST", f"/collections/{COLLECTION}/snapshots?wait=true"))
    name = snap["result"]["name"]
    data = qdrant(stack.qdrant_url, key, "GET", f"/collections/{COLLECTION}/snapshots/{name}")
    (out / "qdrant" / f"{COLLECTION}.snapshot").write_bytes(data)
    qdrant(stack.qdrant_url, key, "DELETE", f"/collections/{COLLECTION}/snapshots/{name}?wait=true")


def qdrant_restore(url: str, key: str, folder: Path, force: bool) -> None:
    cols = json.loads(qdrant(url, key, "GET", "/collections"))["result"]["collections"]
    if any(c["name"] == COLLECTION for c in cols) and not force:
        raise SystemExit(f"Qdrant at {url} already has {COLLECTION}: pass --yes to replace it")
    boundary = uuid.uuid4().hex
    data = (folder / f"{COLLECTION}.snapshot").read_bytes()
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"snapshot\"; filename=\"{COLLECTION}.snapshot\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    qdrant(url, key, "POST", f"/collections/{COLLECTION}/snapshots/upload?priority=snapshot&wait=true", body,
           ctype=f"multipart/form-data; boundary={boundary}", timeout=900)


# ---------------------------------------------------------------- files
def _owned(ti: tarfile.TarInfo) -> tarfile.TarInfo:
    ti.uid = ti.gid = RUNTIME_UID
    ti.uname = ti.gname = "portpilot"
    return ti


def files_backup(stack: Stack, out: Path, with_models: bool) -> list[str]:
    (out / "files").mkdir(parents=True)
    wanted = list(FILES) + (list(MODEL_FILES) if with_models else [])
    present: list[str] = []
    target = out / "files" / "runtime.tar.gz"
    with tarfile.open(target, "w:gz") as tar:
        for rel in wanted:
            if stack.local:
                src = ROOT / rel
                if src.exists():
                    tar.add(src, arcname=rel, filter=_owned)
                    present.append(rel)
                continue
            r = sh(["docker", "cp", f"{stack.api}:/app/{rel}", "-"], check=False)
            if r.returncode != 0:
                continue                           # not there (e.g. no Data/incoming yet)
            with tarfile.open(fileobj=io.BytesIO(r.stdout)) as part:
                base = Path(rel).name
                for m in part.getmembers():
                    inner = m.name[len(base):].lstrip("/") if m.name.startswith(base) else m.name
                    m.name = f"{rel}/{inner}" if inner else rel
                    fobj = part.extractfile(m) if m.isfile() else None
                    tar.addfile(_owned(m), fobj)
            present.append(rel)
    return present


def files_restore(api_container: str, archive: Path) -> None:
    """`docker cp -a` keeps the archive's owner (the runtime user) inside the target volumes. The api container
    mounts the model folder read-only, so model files (a `--with-models` backup) are left out here and seeded by the
    runbook's `ops` command instead."""
    # one stream per volume (a read-only root filesystem refuses a copy to /app itself)
    bufs: dict[str, io.BytesIO] = {}
    tars: dict[str, tarfile.TarFile] = {}
    with tarfile.open(archive) as src:
        for m in src.getmembers():
            mount = next((v for v in VOLUME_DIRS if m.name == v or m.name.startswith(v + "/")), None)
            if mount is None:
                continue                                   # models/, or the parents of a mount point
            inner = m.name[len(mount):].lstrip("/")
            if not inner:
                continue
            if mount not in tars:
                bufs[mount] = io.BytesIO()
                tars[mount] = tarfile.open(fileobj=bufs[mount], mode="w")
            m.name = inner
            tars[mount].addfile(m, src.extractfile(m) if m.isfile() else None)
    for mount, tar in tars.items():
        tar.close()
        sh(["docker", "cp", "-a", "-", f"{api_container}:/app/{mount}"], stdin=bufs[mount].getvalue())


# ---------------------------------------------------------------- commands
def facts(stack: Stack) -> dict:
    return {"postgres": pg_facts(stack.postgres, stack.pg_super),
            "mongo": mongo_facts(stack.mongo, stack.mongo_root()),
            "qdrant": qdrant_facts(stack.qdrant_url, stack.qdrant_key())}


def cmd_backup(stack: Stack, out_root: Path, with_models: bool) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = out_root / f"{stack.name}_{stamp}"
    tmp = out_root / f".{out.name}.partial"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    t0 = time.monotonic()
    # each store's facts right after its own dump: the smallest window for a write in between (a write there shows
    # up as a difference in `restore` / the drill, never silently)
    pg_backup(stack, tmp)
    got = {"postgres": pg_facts(stack.postgres, stack.pg_super)}
    mongo_backup(stack, tmp)
    got["mongo"] = mongo_facts(stack.mongo, stack.mongo_root())
    qdrant_backup(stack, tmp)
    got["qdrant"] = qdrant_facts(stack.qdrant_url, stack.qdrant_key())
    present = files_backup(stack, tmp, with_models)
    manifest = {"created_utc": stamp, "stack": stack.name, "database": DB, "collection": COLLECTION,
                "files_included": present, "with_models": with_models, "facts": got,
                "artifacts": {str(p.relative_to(tmp)).replace("\\", "/"): {"sha256": sha256(p), "bytes": p.stat().st_size}
                              for p in sorted(tmp.rglob("*")) if p.is_file()},
                "seconds": round(time.monotonic() - t0, 1)}
    (tmp / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                                       newline="\n")
    tmp.rename(out)                       # a folder without `.partial` is always complete
    total = sum(a["bytes"] for a in manifest["artifacts"].values())
    print(f"✅ backup {out.name}: {len(manifest['artifacts'])} files, {total / 1e6:.1f} MB, "
          f"{sum(manifest['facts']['postgres']['table_rows'].values())} PostgreSQL rows, "
          f"{sum(manifest['facts']['mongo']['collections'].values())} MongoDB documents, "
          f"{manifest['facts']['qdrant']['points']} Qdrant points ({manifest['seconds']} s)")
    return out


def cmd_verify(folder: Path) -> dict:
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    bad = [rel for rel, a in manifest["artifacts"].items()
           if not (folder / rel).is_file() or sha256(folder / rel) != a["sha256"]]
    if bad:
        raise SystemExit(f"❌ {folder.name}: {len(bad)} file(s) missing or changed: {bad[:5]}")
    with tarfile.open(folder / "files" / "runtime.tar.gz") as tar:
        n = len(tar.getmembers())
    print(f"✅ verify {folder.name}: {len(manifest['artifacts'])} files = the manifest's sha256; runtime archive "
          f"{n} entries")
    return manifest


def compare(expected: dict, got: dict) -> list[str]:
    diffs: list[str] = []
    for store in ("postgres", "mongo", "qdrant"):
        e, g = expected[store], got[store]
        for k in e:
            if e[k] != g.get(k):
                if isinstance(e[k], dict):
                    keys = sorted(set(e[k]) | set(g.get(k, {})))
                    diffs += [f"{store}.{k}.{x}: {e[k].get(x)} ≠ {g.get(k, {}).get(x)}" for x in keys
                              if e[k].get(x) != g.get(k, {}).get(x)]
                else:
                    diffs.append(f"{store}.{k}: {e[k]} ≠ {g.get(k)}")
    return diffs


def cmd_restore(folder: Path, stack: Stack, force: bool) -> None:
    if stack.local:
        raise SystemExit("restore never targets the owner's local stores (`local`): use a deployment stack or `drill`")
    manifest = cmd_verify(folder)
    pg_restore(stack.postgres, stack.pg_super, folder / "postgres", force)
    mongo_restore(stack.mongo, stack.mongo_root(), folder / "mongo", force)
    qdrant_restore(stack.qdrant_url, stack.qdrant_key(), folder / "qdrant", force)
    assert stack.api is not None
    files_restore(stack.api, folder / "files" / "runtime.tar.gz")
    diffs = compare(manifest["facts"], facts(stack))
    if diffs:
        raise SystemExit(f"❌ restore into {stack.name}: {len(diffs)} difference(s): {diffs[:8]}")
    print(f"✅ restore {folder.name} → {stack.name}: every table count, the kpi_weekly digest, every MongoDB count, "
          f"the Qdrant points and their digest = the backup")


def cmd_secure(stack: Stack) -> None:
    """After a restore into a new environment: its own passwords, no inherited sign-in (S7)."""
    if stack.local:
        raise SystemExit("secure is for a deployment stack, never `local`")
    e = stack.env
    for user_var, pwd_var in RUNTIME_LOGINS:
        user, pwd = e.get(user_var), e.get(pwd_var)
        if not (user and pwd):
            raise SystemExit(f"{user_var} / {pwd_var} missing in {stack.env_file}")
        sh(["docker", "exec", "-i", stack.postgres, "psql", "-U", stack.pg_super, "-d", "postgres", "-X", "-q",
            "-v", "ON_ERROR_STOP=1"],
           stdin=f"ALTER ROLE \"{user}\" WITH LOGIN PASSWORD '{pwd.replace(chr(39), chr(39) * 2)}';\n".encode())
    n = psql(stack.postgres, stack.pg_super,
             "WITH d AS (UPDATE api.logins SET disabled = true WHERE NOT disabled RETURNING 1), "
             "t AS (UPDATE api.tokens SET revoked_at = now() WHERE revoked_at IS NULL RETURNING 1) "
             "SELECT (SELECT count(*) FROM d) || ' logins disabled, ' || (SELECT count(*) FROM t) || ' tokens revoked'")
    creds = stack.mongo_root()
    users = {"NG_APP_USER": e.get("MONGO_APP_USER", ""), "NG_APP_PWD": e.get("MONGO_APP_PASSWORD", ""),
             "NG_RO_USER": e.get("MONGO_RO_USER", ""), "NG_RO_PWD": e.get("MONGO_RO_PASSWORD", "")}
    if not all(users.values()):
        raise SystemExit("MONGO_APP_USER / _PASSWORD and MONGO_RO_USER / _PASSWORD are needed in the env file")
    js = (f"const a = db.getSiblingDB('admin'); const e = process.env;"
          f"[[e.NG_APP_USER, e.NG_APP_PWD, 'readWrite'], [e.NG_RO_USER, e.NG_RO_PWD, 'read']].forEach(([u, p, r]) => {{"
          f" const roles = [{{role: r, db: '{DB}'}}];"
          " if (a.getUser(u)) a.updateUser(u, {pwd: p, roles: roles}); else a.createUser({user: u, pwd: p, roles: roles});"
          "}); print('ok');")
    sh(["docker", "exec", "-e", "NG_ROOT_USER", "-e", "NG_ROOT_PWD", "-e", "NG_APP_USER", "-e", "NG_APP_PWD",
        "-e", "NG_RO_USER", "-e", "NG_RO_PWD", stack.mongo, "sh", "-c",
        'mongosh --quiet -u "$NG_ROOT_USER" -p "$NG_ROOT_PWD" --authenticationDatabase admin --eval "$0"', js],
       env={**creds, **users})
    print(f"✅ secure {stack.name}: {len(RUNTIME_LOGINS)} PostgreSQL runtime logins re-keyed from the env file; {n}; "
          "MongoDB app + reader users set; next: Api_admin.py create / enable for the real people")


def cmd_prune(out_root: Path, daily: int, weekly: int, dry_run: bool) -> None:
    folders = sorted((p for p in out_root.glob("*_20*") if p.is_dir() and (p / "manifest.json").exists()),
                     key=lambda p: p.name.rsplit("_", 1)[-1], reverse=True)
    keep: set[Path] = set(folders[:daily])
    weeks: dict[str, Path] = {}
    for p in folders:
        stamp = datetime.strptime(p.name.rsplit("_", 1)[-1], "%Y%m%dT%H%M%SZ")
        weeks.setdefault(f"{stamp.isocalendar()[0]}-W{stamp.isocalendar()[1]:02d}", p)
    keep |= set(list(weeks.values())[:weekly])
    drop = [p for p in folders if p not in keep]
    for p in drop:
        print(f"{'would delete' if dry_run else 'deleted'} {p.name}")
        if not dry_run:
            shutil.rmtree(p)
    print(f"✅ prune: kept {len(keep)}, {'would delete' if dry_run else 'deleted'} {len(drop)}")


def wait_until(check, what: str, seconds: int = 180) -> None:
    for _ in range(seconds):
        try:
            if check():
                return
        except (SystemExit, OSError, urllib.error.URLError):
            pass
        time.sleep(1)
    raise SystemExit(f"{what} did not become ready")


def cmd_drill(keep: bool, out_root: Path) -> None:
    """The restore drill (stabilization Phase 5): the owner's stores → a backup → three fresh containers on other
    loopback ports → restore → the same facts. The owner's containers are only read."""
    local = Stack("local", None)
    folder = cmd_backup(local, out_root, with_models=False)
    images = {c: sh(["docker", "inspect", c, "--format", "{{.Config.Image}}"]).stdout.decode().strip()
              for c in (local.postgres, local.mongo, local.qdrant)}
    pre = "portpilot-drill"
    pg_pwd, mg_pwd, qd_key = (secrets.token_urlsafe(24) for _ in range(3))
    names = [f"{pre}-postgres", f"{pre}-mongo", f"{pre}-qdrant"]
    existing = sh(["docker", "ps", "-a", "--format", "{{.Names}}"]).stdout.decode().split()
    if any(n in existing for n in names):
        raise SystemExit(f"a drill container already exists: docker rm -f {' '.join(names)}")
    env = {"NG_PG": pg_pwd, "NG_MG": mg_pwd, "NG_QD": qd_key}
    try:
        sh(["docker", "run", "-d", "--name", names[0], "-p", "127.0.0.1:55433:5432", "-e", "POSTGRES_USER=postgres",
            "-e", "POSTGRES_PASSWORD", images[local.postgres]], env={"POSTGRES_PASSWORD": pg_pwd, **env})
        sh(["docker", "run", "-d", "--name", names[1], "-p", "127.0.0.1:27018:27017",
            "-e", "MONGO_INITDB_ROOT_USERNAME=drill", "-e", "MONGO_INITDB_ROOT_PASSWORD", images[local.mongo]],
           env={"MONGO_INITDB_ROOT_PASSWORD": mg_pwd})
        sh(["docker", "run", "-d", "--name", names[2], "-p", "127.0.0.1:16343:6333", "-e", "QDRANT__SERVICE__API_KEY",
            "-e", "QDRANT__TELEMETRY_DISABLED=true", images[local.qdrant]], env={"QDRANT__SERVICE__API_KEY": qd_key})

        def pg_ready() -> bool:
            logs = sh(["docker", "logs", names[0]], check=False)
            text = (logs.stdout + logs.stderr).decode("utf-8", "replace")
            return ("PostgreSQL init process complete" in text
                    and sh(["docker", "exec", names[0], "pg_isready", "-U", "postgres"], check=False).returncode == 0)
        wait_until(pg_ready, names[0])
        creds = {"NG_ROOT_USER": "drill", "NG_ROOT_PWD": mg_pwd}
        wait_until(lambda: mongosh(names[1], creds, "print(db.adminCommand({ping: 1}).ok)").endswith("1"), names[1])
        url = "http://127.0.0.1:16343"
        wait_until(lambda: json.loads(qdrant(url, qd_key, "GET", "/collections"))["status"] == "ok", names[2])
        t0 = time.monotonic()
        manifest = cmd_verify(folder)
        pg_restore(names[0], "postgres", folder / "postgres", force=False)
        mongo_restore(names[1], creds, folder / "mongo", force=False)
        qdrant_restore(url, qd_key, folder / "qdrant", force=False)
        with tempfile.TemporaryDirectory() as tmp:
            with tarfile.open(folder / "files" / "runtime.tar.gz") as tar:
                tar.extractall(tmp, filter="data")
            restored = sorted(str(p.relative_to(tmp)).replace("\\", "/") for p in Path(tmp).rglob("*") if p.is_file())
            original = sorted(str(p.relative_to(ROOT)).replace("\\", "/") for rel in manifest["files_included"]
                              for p in ([ROOT / rel] if (ROOT / rel).is_file() else (ROOT / rel).rglob("*"))
                              if p.is_file())
            same = restored == original and all(sha256(Path(tmp) / r) == sha256(ROOT / r) for r in restored)
        got = {"postgres": pg_facts(names[0], "postgres"), "mongo": mongo_facts(names[1], creds),
               "qdrant": qdrant_facts(url, qd_key)}
        diffs = compare(manifest["facts"], got)
        if not same:
            diffs.append("files: the restored runtime files differ from the working tree")
        seconds = round(time.monotonic() - t0, 1)
        report = {"drill_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "backup": folder.name,
                  "restore_seconds": seconds, "differences": diffs, "facts": got,
                  "files_restored": len(restored), "files_identical": same}
        (folder / "drill_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n",
                                                  encoding="utf-8", newline="\n")
        if diffs:
            raise SystemExit(f"❌ drill: {len(diffs)} difference(s): {diffs[:8]}")
        pg_rows = sum(got["postgres"]["table_rows"].values())
        print(f"✅ drill: restored in {seconds} s into fresh containers — {len(got['postgres']['table_rows'])} tables / "
              f"{pg_rows} rows, kpi_weekly digest equal; {sum(got['mongo']['collections'].values())} MongoDB "
              f"documents in {len(got['mongo']['collections'])} collections; {got['qdrant']['points']} Qdrant points, "
              f"digest equal; {len(restored)} runtime files byte-identical")
    finally:
        if not keep:
            sh(["docker", "rm", "-f", *names], check=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backup")
    b.add_argument("--stack", required=True)
    b.add_argument("--env-file", type=Path)
    b.add_argument("--out", type=Path, default=ROOT / "backups")
    b.add_argument("--with-models", action="store_true")
    v = sub.add_parser("verify")
    v.add_argument("folder", type=Path)
    r = sub.add_parser("restore")
    r.add_argument("folder", type=Path)
    r.add_argument("--stack", required=True)
    r.add_argument("--env-file", type=Path, required=True)
    r.add_argument("--yes", action="store_true", help="replace a target that already holds data")
    s = sub.add_parser("secure")
    s.add_argument("--stack", required=True)
    s.add_argument("--env-file", type=Path, required=True)
    p = sub.add_parser("prune")
    p.add_argument("--out", type=Path, default=ROOT / "backups")
    p.add_argument("--daily", type=int, default=7)
    p.add_argument("--weekly", type=int, default=4)
    p.add_argument("--dry-run", action="store_true")
    d = sub.add_parser("drill")
    d.add_argument("--keep", action="store_true", help="leave the drill containers running for inspection")
    d.add_argument("--out", type=Path, default=ROOT / "backups")
    a = ap.parse_args()
    if a.cmd == "backup":
        cmd_backup(Stack(a.stack, a.env_file), a.out, a.with_models)
    elif a.cmd == "verify":
        cmd_verify(a.folder)
    elif a.cmd == "restore":
        cmd_restore(a.folder, Stack(a.stack, a.env_file), a.yes)
    elif a.cmd == "secure":
        cmd_secure(Stack(a.stack, a.env_file))
    elif a.cmd == "prune":
        cmd_prune(a.out, a.daily, a.weekly, a.dry_run)
    else:
        cmd_drill(a.keep, a.out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    main()
