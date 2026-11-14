"""Cross-process safety for the append-only JSONL caches (FastAPI plan C3 / C4): the LLM reply cache, the external
tool cache and the JSON quota state were written by one process at a time (a CLI); the API runs beside the
scheduled CLIs, so several processes — and several threads of one — now write them.

- `append_line`: one whole line appended under an OS file lock (`filelock`, `<file>.lock`), so lines never interleave.
- `Tail`: reads only the lines appended since the last read and only complete ones (a writer between two reads leaves
  a partial last line, read next time), so a process sees another's new entries without re-reading the whole file.
- `flight`: single-flight per key — a thread lock inside the process plus a striped file lock across processes
  (4,096 stripes by the key's first three hex digits: unrelated keys rarely share one, the lock files stay few).
- `update_json`: read-modify-write of a small JSON state file under its lock, re-read from disk first.
The files stay where and what they were (replay determinism and the evaluation tooling unchanged).
"""
import json
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock

LOCK_TIMEOUT_S = 300           # longer than any single model call (llm.TIMEOUT_S 120 + one rate wait 60)
STRIPE_HEX = 3


def lock_for(path: Path) -> FileLock:
    return FileLock(str(path) + ".lock", timeout=LOCK_TIMEOUT_S)


def append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (line.rstrip("\n") + "\n").encode("utf-8")
    with lock_for(path), path.open("ab") as f:
        f.write(data)


class Tail:
    """The JSON records of an append-only JSONL file, read incrementally."""

    def __init__(self, path: Path):
        self.path, self.offset = path, 0

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open("rb") as f:
            f.seek(self.offset)
            chunk = f.read()
        end = chunk.rfind(b"\n") + 1             # complete lines only
        self.offset += end
        return [json.loads(line) for line in chunk[:end].decode("utf-8").splitlines() if line.strip()]


_thread_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()


@contextmanager
def flight(folder: Path, key: str) -> Iterator[None]:
    """Held while one process computes the value of `key`; the others wait, then find it in the cache."""
    stripe = key[:STRIPE_HEX]
    path = folder / "locks" / f"{stripe}.lock"
    with _guard:
        tl = _thread_locks.setdefault(str(path), threading.Lock())
    path.parent.mkdir(parents=True, exist_ok=True)
    with tl, FileLock(str(path), timeout=LOCK_TIMEOUT_S):
        yield


def update_json(path: Path, change: Callable[[dict], object]) -> tuple[dict, object]:
    """(the new content, what `change` returned): `change` edits the freshly read dict in place, under the lock;
    the file is replaced atomically (LF, sorted keys — the format the quota files always had)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with lock_for(path):
        obj = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        out = change(obj)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj, indent=1, sort_keys=True), encoding="utf-8", newline="\n")
        tmp.replace(path)
    return obj, out


def read_json(path: Path) -> dict:
    """A consistent snapshot, read under the lock: on Windows a writer's atomic replace fails while another process
    holds the file open, so readers and writers take turns."""
    with lock_for(path):
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
