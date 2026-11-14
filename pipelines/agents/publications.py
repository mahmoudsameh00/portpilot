"""Complete immutable pack versions, an atomic current pointer, and recoverable approved-row sync.

No database/schema ownership here: the caller supplies the existing transactional store_approved operation.
The filesystem lock serializes publication and reconciliation of one week across API/CLI processes on this host.
Legacy week folders remain readable; they are never silently rewritten or declared synchronized.
"""
import hashlib
import json
import logging
import os
import re
import tempfile
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock

FILES = {"deck.pptx", "deck_draft.json", "approval.json", "run.json"}
POINTER = "publication.json"
log = logging.getLogger(__name__)


def encoded(value: object) -> bytes:
    return (json.dumps(value, indent=1, ensure_ascii=False, sort_keys=True, default=str) + "\n").encode("utf-8")


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    """Same-directory replacement: readers see the complete old or new manifest, never a partial JSON write."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".manifest-", suffix=".tmp", delete=False) as file:
            temporary = Path(file.name)
            file.write(encoded(value))
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def current(week_folder: Path) -> tuple[dict | None, Path]:
    """Resolve once and verify the immutable version; a corrupt pointer never falls back to an older pack."""
    path = week_folder / POINTER
    if not path.exists():
        return None, week_folder
    manifest = json.loads(path.read_text(encoding="utf-8"))
    ident = manifest.get("publication_id", "")
    if (manifest.get("version") != 1 or not isinstance(ident, str) or not re.fullmatch(r"[0-9a-f]{32}", ident)
            or set(manifest.get("files") or {}) != FILES
            or (manifest.get("db_sync") or {}).get("status") not in ("pending", "synced", "not_required")):
        raise ValueError("invalid publication manifest")
    folder = week_folder / "_publications" / ident
    if not folder.resolve().is_relative_to(week_folder.resolve()):
        raise ValueError("publication folder escapes the report week")
    for name, sha in manifest["files"].items():
        if digest((folder / name).read_bytes()) != sha:
            raise ValueError(f"publication integrity check failed: {name}")
    run = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    if run.get("thread_id") != manifest.get("thread_id") or run.get("report_week") != manifest.get("report_week"):
        raise ValueError("publication manifest does not identify its run")
    return manifest, folder


def sync_status(week_folder: Path, thread_id: str | None = None) -> str:
    manifest, _ = current(week_folder)
    if manifest is None:
        return "unknown"
    if thread_id is not None and manifest["thread_id"] != thread_id:
        return "superseded"
    return manifest["db_sync"]["status"]


def _sync(week_folder: Path, manifest: dict, folder: Path, store: Callable[[dict], None] | None,
          check_active: Callable[[], None]) -> dict:
    if manifest["db_sync"]["status"] != "pending":
        return manifest
    if store is None:
        raise ValueError("a pending publication requires its approved-row writer")
    check_active()
    run = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    sync = {"status": "pending", "attempts": manifest["db_sync"]["attempts"] + 1, "last_attempt_at": stamp()}
    try:
        store(run)
    except Exception as exc:  # noqa: BLE001 — saved deck stays available; retry uses the same approved payload
        sync["error"] = type(exc).__name__  # no connection strings or arbitrary exception text in public metadata
        log.warning("Pack %s database sync pending (%s); reconcile the saved publication", run["thread_id"], sync["error"])
    else:
        sync["status"] = "synced"
    updated = {**manifest, "db_sync": sync}
    # A crash after the DB commit leaves pending on disk. Retrying is safe: the writer replaces one week's rows
    # in a transaction using this exact approved payload; it never reads a newly edited graph state.
    atomic_json(week_folder / POINTER, updated)
    return updated


def publish(week_folder: Path, files: dict[str, bytes], input_sha: str, store: Callable[[dict], None] | None,
            check_active: Callable[[], None]) -> tuple[dict, Path]:
    if set(files) != FILES:
        raise ValueError("a publication must contain the complete four-file pack")
    run = json.loads(files["run.json"])
    if not run.get("thread_id") or run.get("deck_sha256") != digest(files["deck.pptx"]):
        raise ValueError("the publication must identify its thread and verified deck hash")
    week_folder.mkdir(parents=True, exist_ok=True)
    with FileLock(str(week_folder / ".publication.lock"), timeout=0):
        old, folder = current(week_folder)
        if old and old.get("input_sha") == input_sha:
            return _sync(week_folder, old, folder, store, check_active), folder
        ident = uuid.uuid4().hex
        folder = week_folder / "_publications" / ident
        folder.parent.mkdir(exist_ok=True)
        manifest = {"version": 1, "publication_id": ident, "input_sha": input_sha,
                    "thread_id": run["thread_id"], "report_week": run["report_week"], "at": stamp(),
                    "files": {name: digest(data) for name, data in files.items()},
                    "db_sync": {"status": "pending" if store else "not_required", "attempts": 0}}
        with tempfile.TemporaryDirectory(prefix=".publishing-", dir=week_folder) as temporary:
            staging = Path(temporary)
            for name, data in files.items():
                with (staging / name).open("wb") as file:
                    file.write(data)
                    file.flush()
                    os.fsync(file.fileno())
                if digest((staging / name).read_bytes()) != manifest["files"][name]:
                    raise ValueError(f"publication staging verification failed: {name}")
            check_active()
            os.replace(staging, folder)
        check_active()
        atomic_json(week_folder / POINTER, manifest)
        return _sync(week_folder, manifest, folder, store, check_active), folder


def reconcile(week_folder: Path, store: Callable[[dict], None], check_active: Callable[[], None] = lambda: None) -> dict:
    """Retry only the current approved version under the same week lock; never resume or approve a graph."""
    if not week_folder.is_dir():
        raise ValueError("no published pack for this week")
    with FileLock(str(week_folder / ".publication.lock"), timeout=0):
        manifest, folder = current(week_folder)
        if manifest is None:
            raise ValueError("legacy publication has no verified manifest; inspect it before migrating its approved rows")
        return _sync(week_folder, manifest, folder, store, check_active)
