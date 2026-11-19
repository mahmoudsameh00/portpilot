"""Which migrations a database holds, and the deploy's way to apply the pending ones (Staging readiness plan P7,
ADR-071, ADR-016 amendment 1). The record is `public.schema_migrations` (migration 031).

Commands (from the project root; the owner account PGUSER / PGPASSWORD of the environment — locally `.env`, in a
deployment the `migrate` service of deploy/compose.yaml):
    python pipelines/scripts/ops/Migrate.py status            read-only: recorded / pending / edited files; exit 0
                                                              when nothing is pending, 3 when files are pending,
                                                              4 when a recorded hash no longer matches its file
    python pipelines/scripts/ops/Migrate.py apply --yes        apply every pending file in order, each as its own
                                                              script (the files hold their own BEGIN / COMMIT), and
                                                              record it; stops at the first error
    python pipelines/scripts/ops/Migrate.py apply --yes --to 31   … up to a number
A database without the record table but with migration 030's table is bootstrapped by applying 031 first.
On the owner's machine migrations stay applied by the owner (db/README.md); in staging / production the deploy
workflow runs `apply` only after the owner's approval of the migrations step (ADR-071).

Reads:   db/migrations/*.sql, public.schema_migrations. Writes: only `apply` — the migrations and their rows.
Re-run:  safe: `apply` with nothing pending changes nothing.
"""
import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

import psycopg

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))
from pipelines.lib.common import load_env  # noqa: E402

MIGRATIONS = ROOT / "db" / "migrations"
NAME = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")
RECORD = 31


def text_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def files() -> dict[int, Path]:
    out: dict[int, Path] = {}
    for p in sorted(MIGRATIONS.glob("*.sql")):
        m = NAME.match(p.name)
        if not m:
            raise SystemExit(f"unexpected file name in db/migrations: {p.name}")
        n = int(m.group(1))
        if n in out:
            raise SystemExit(f"two migrations numbered {n:03d}: {out[n].name}, {p.name}")
        out[n] = p
    gaps = [n for n in range(1, max(out) + 1) if n not in out]
    if gaps:
        raise SystemExit(f"migration numbers missing: {gaps}")
    return out


def connect() -> psycopg.Connection:
    load_env(ROOT)
    e = os.environ
    return psycopg.connect(host=e["PGHOST"], port=e["PGPORT"], dbname=e["PGDATABASE"], user=e["PGUSER"],
                           password=e.get("PGPASSWORD", ""), autocommit=True, connect_timeout=10)


def recorded(conn) -> dict[int, tuple[str, str | None]] | None:
    if conn.execute("SELECT to_regclass('public.schema_migrations')").fetchone()[0] is None:
        return None
    return {int(v): (f, h) for v, f, h in conn.execute("SELECT version, filename, sha256 FROM public.schema_migrations")}


def state(conn) -> tuple[dict[int, Path], dict[int, tuple[str, str | None]] | None, list[int], list[str]]:
    fs = files()
    rec = recorded(conn)
    if rec is None:
        bootstrap = conn.execute("SELECT to_regclass('public.port_call_messages')").fetchone()[0] is not None
        pending = [n for n in fs if n >= RECORD] if bootstrap else sorted(fs)
        return fs, None, pending, []
    edited = [f"{n:03d} {fs[n].name}" for n, (_f, h) in sorted(rec.items())
              if n in fs and h is not None and h != text_hash(fs[n])]
    edited += [f"{n:03d} recorded but no file ({f})" for n, (f, _h) in sorted(rec.items()) if n not in fs]
    pending = [n for n in sorted(fs) if n not in rec]
    return fs, rec, pending, edited


def cmd_status(conn) -> int:
    fs, rec, pending, edited = state(conn)
    if rec is None:
        print(f"no public.schema_migrations yet: {len(fs)} files; pending from {pending[0]:03d}"
              + (" (bootstrap: 001–030 already applied)" if pending and pending[0] == RECORD else ""))
    else:
        print(f"recorded {len(rec)} of {len(fs)} files (last {max(rec):03d})")
    for n in pending:
        print(f"  pending  {fs[n].name}")
    for line in edited:
        print(f"  EDITED   {line}  ← a recorded migration no longer matches its file")
    if edited:
        return 4
    return 3 if pending else 0


def cmd_apply(conn, upto: int | None) -> int:
    fs, rec, pending, edited = state(conn)
    if edited:
        print("refused: a recorded migration was edited (run status); nothing applied")
        return 4
    todo = [n for n in pending if upto is None or n <= upto]
    for n in todo:
        path = fs[n]
        print(f"applying {path.name} …", flush=True)
        conn.execute(path.read_text(encoding="utf-8"))
        h = text_hash(path)
        conn.execute("INSERT INTO public.schema_migrations (version, filename, sha256, note) VALUES (%s, %s, %s, %s) "
                     "ON CONFLICT (version) DO UPDATE SET sha256 = EXCLUDED.sha256, note = EXCLUDED.note",
                     (n, path.name, h, "applied by Migrate.py"))
    # 031 records itself without a hash; fill it (and any other NULL) now
    for n, (_f, h) in (recorded(conn) or {}).items():
        if h is None and n in fs:
            conn.execute("UPDATE public.schema_migrations SET sha256 = %s WHERE version = %s AND sha256 IS NULL",
                         (text_hash(fs[n]), n))
    print(f"✅ applied {len(todo)} migration(s)" + (f": {', '.join(f'{n:03d}' for n in todo)}" if todo else ""))
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    a_ = sub.add_parser("apply")
    a_.add_argument("--yes", action="store_true", help="confirm: this changes the database")
    a_.add_argument("--to", type=int, help="apply up to this number only")
    a = ap.parse_args()
    with connect() as conn:
        if a.cmd == "status":
            sys.exit(cmd_status(conn))
        if not a.yes:
            sys.exit("apply changes the database: add --yes (the deploy passes it after the owner's approval)")
        sys.exit(cmd_apply(conn, a.to))


if __name__ == "__main__":
    main()
