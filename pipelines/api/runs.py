"""Graph runs outside the request (FastAPI plan §4 C5 / C7 / C8 / C9, §5): a POST answers 202 with a run id at once;
the work runs in a bounded thread pool; its events wait in the run's buffer for the SSE stream (or `GET /runs/{id}`).

- **Slots and queue:** `RUN_SLOTS` threads run graphs; at most `RUN_QUEUE` more wait. Beyond that → 429 + Retry-After.
- **Per-employee limits** (plan A7): questions and route advices per hour, sliding, per process → 429 + Retry-After.
- **One run per conversation** at a time (a follow-up needs the answer before it) → 409; **one run per graph thread**
  across processes (`thread_lock`: a PostgreSQL advisory lock on a connection of its own, so the API and a CLI never
  resume one pack thread together) → 409.
- **Time limit:** a run past its limit is reported `failed: timeout` at once; its thread finishes in the background and
  its result is dropped (the graph's checkpoint keeps what it did, as after a crashed CLI run). Running workers
  retain capacity until they exit; expired queued Futures are cancelled before executing.
- **End order** (D-F2): record (`on_finish`) → free the conversation → publish `done` / `failed`, so whatever a client
  reads or asks after the last event sees the run's end stored.
- **Events** (§5): appended with an increasing id, checked against the contract (`schemas.EVENT_FIELDS`), kept with
  the run for `KEEP_FINISHED` after it ends; a run belongs to its owner only (another employee → 404).
"""
import logging
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone

import psycopg

from pipelines.agents import locks
from pipelines.api import schemas
from pipelines.api.errors import ApiError

RUN_SLOTS = 4
RUN_QUEUE = 20
KEEP_FINISHED_S = 3600
MAX_EVENTS = 500
LIMITS_PER_HOUR = {"ask": 30, "route_advice": 10, "view": 30,   # view: a question in words (one model call)
                   "pack_request": 20}                           # the manager's request read (approver-request plan)
TIMEOUT_S = {"ask": 180, "route_advice": 120, "pack_decision": 300, "view": 60,   # a revise re-drafts (plan D)
             "pack_request": 60}

log = logging.getLogger(__name__)


def _problem(status: int, slug: str, detail: str) -> dict:
    return {"type": f"urn:portpilot:problem:{slug}", "status": status, "detail": detail[:300]}


@dataclass
class Event:
    id: int
    event: str
    data: dict


@dataclass
class Run:
    id: str
    owner: int
    kind: str
    thread_id: str | None
    conversation_id: str | None = None
    state: str = "queued"                       # queued → running → done | failed
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    result: dict | None = None
    error: dict | None = None
    events: list[Event] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _claimed: bool = field(default=False, repr=False)

    def start(self) -> bool:
        """An expired queue entry must never become running."""
        with self._lock:
            if self._claimed:
                return False
            self.state = "running"
            return True

    def check_active(self) -> None:
        """Cooperative guard for callers before another expensive or mutating operation."""
        with self._lock:
            if self._claimed:
                raise ApiError(504, "the run has expired", slug="timeout")

    def claim(self) -> bool:
        """Reserves the run's end for one caller — its thread or the time limit, whichever comes first (D-F2). The
        winner records what it must (the turn's status) and frees the conversation *before* `finish` publishes the
        end, so a client that sees `done` reads a stored turn and may ask its follow-up at once."""
        with self._lock:
            if self._claimed:
                return False
            self._claimed = True
            return True

    def emit(self, event: str, data: dict) -> None:
        schemas.check_event(event, data)        # the contract: an unknown event or field is a bug, not a message
        with self._lock:
            if self.finished_at is not None and event not in ("answer", "done", "failed"):
                return                          # a timed-out run's thread may still be talking: dropped (its answer
                                                # is sent only by the run that won `finish`)
            if len(self.events) < MAX_EVENTS or event in ("answer", "done", "failed"):
                self.events.append(Event(len(self.events) + 1, event, data))

    def since(self, last_id: int) -> list[Event]:
        with self._lock:
            return [e for e in self.events if e.id > last_id]

    def finish(self, state: str, result: dict | None = None, error: dict | None = None) -> bool:
        """False when the run had already finished (a timeout came first)."""
        with self._lock:
            if self.finished_at is not None:
                return False
            self.state, self.result, self.error = state, result, error
            self.finished_at = datetime.now(timezone.utc)
        return True

    @property
    def finished(self) -> bool:
        return self.finished_at is not None


class Runner:
    def __init__(self, slots: int = RUN_SLOTS, queue: int = RUN_QUEUE):
        self.slots, self.queue = slots, queue
        self.pool = ThreadPoolExecutor(max_workers=slots, thread_name_prefix="run")
        self.runs: dict[str, Run] = {}
        self._lock = threading.Lock()
        self._recent: dict[tuple[int, str], deque] = {}
        self._busy_conversations: set[str] = set()
        self._reserved_threads: set[str] = set()
        self._inflight: dict[str, Future] = {}
        self._occupied: set[str] = set()
        self._released: set[str] = set()
        self._closed = False

    # --- admission (C8) ---------------------------------------------------------------------------------------------
    def _active(self) -> list[Run]:
        return [self.runs[rid] for rid in self._occupied]

    def _admit(self, owner: int, kind: str, conversation_id: str | None) -> None:
        now = time.monotonic()
        if self._closed:
            raise ApiError(503, "the API is shutting down", slug="shutdown")
        if len(self._active()) >= self.slots + self.queue:
            raise ApiError(429, "the API is busy; try again shortly", slug="queue_full", headers={"Retry-After": "30"})
        if conversation_id is not None and conversation_id in self._busy_conversations:
            raise ApiError(409, "this conversation is still answering its last question", slug="busy")
        limit = LIMITS_PER_HOUR.get(kind)
        if limit is not None:
            q = self._recent.setdefault((owner, kind), deque())
            while q and now - q[0] >= 3600:
                q.popleft()
            if len(q) >= limit:
                wait = int(3600 - (now - q[0])) + 1
                raise ApiError(429, f"at most {limit} {kind.replace('_', ' ')} requests an hour", slug="rate_limited",
                               headers={"Retry-After": str(wait)})
            q.append(now)
        if conversation_id is not None:
            self._busy_conversations.add(conversation_id)       # released when the run's thread ends (not at timeout)

    @contextmanager
    def conversation(self, conversation_id: str) -> Iterator[None]:
        """Holds a conversation busy for work outside a run (an upload): a question meanwhile → 409, and back."""
        with self._lock:
            if conversation_id in self._busy_conversations:
                raise ApiError(409, "this conversation is busy (a question or an upload)", slug="busy")
            self._busy_conversations.add(conversation_id)
        try:
            yield
        finally:
            with self._lock:
                self._busy_conversations.discard(conversation_id)

    def reserve_thread(self, make: Callable[[], str]) -> str:
        """A new thread id no other run of this process holds (`new_thread_id` reads the checkpoints, which a run
        not yet started has not written): `make()` until free, under the runner's lock."""
        with self._lock:
            tid = make()
            while tid in self._reserved_threads:
                head, _, n = tid.rpartition(":")
                tid = f"{head}:{int(n) + 1}" if n.isdigit() else f"{tid}-{uuid.uuid4().hex[:4]}"
            self._reserved_threads.add(tid)
            return tid

    # --- the run itself (C7) ----------------------------------------------------------------------------------------
    def submit(self, owner: int, kind: str, work: Callable[[Run], dict], *, thread_id: str | None = None,
               conversation_id: str | None = None,
               on_finish: Callable[[str, dict | None], None] | None = None) -> Run:
        """`on_finish(state, result)` runs once when work ends (or its queued Future is cancelled), before the conversation is freed
        and before `done` / `failed` is published (D-F2): `state` is "done" with `work`'s result, or "failed" (an
        error, or the time limit came first: the client was told `failed`, so the record says so too)."""
        with self._lock:
            self._sweep()
            try:
                self._admit(owner, kind, conversation_id)
            except Exception:
                if thread_id:
                    self._reserved_threads.discard(thread_id)
                raise
            run = Run(uuid.uuid4().hex, owner, kind, thread_id, conversation_id)
            run.emit("queued", {"position": max(0, len(self._active()) - self.slots)})
            self.runs[run.id] = run
            self._occupied.add(run.id)
        timeout = TIMEOUT_S.get(kind, 120)
        watchdog = threading.Timer(timeout, self._timeout, args=(run,))
        watchdog.daemon = True

        def record(state: str, result: dict | None) -> dict | None:
            try:
                if on_finish is not None:
                    on_finish(state, result)
            except Exception:  # noqa: BLE001 — a lost record is a visible failure
                log.exception("run %s (%s): on_finish failed", run.id, run.kind)
                return _problem(500, "record_failed", "the run's final record could not be saved")
            return None

        def body() -> None:
            result: dict | None = None
            problem: dict | None = None
            try:
                # submit registers the Future under this lock before any worker can enter.
                with self._lock:
                    started = run.start()
                if started:
                    run.emit("started", {"thread_id": run.thread_id, "graph": kind})
                    result = work(run)
                    try:
                        result = schemas.AnswerData.model_validate(result).model_dump(mode="json")
                    except ValueError as exc:
                        raise schemas.ContractError("invalid worker answer") from exc
            except ApiError as exc:
                problem = _problem(exc.status, exc.slug, exc.detail)
            except Exception as exc:  # noqa: BLE001 — mapped to the same problem bodies as a request (errors.py)
                problem = _problem(*failure(exc, run_id=run.id, thread_id=run.thread_id, run_kind=run.kind))
            won = run.claim()                   # False: the time limit came first and has already said `failed`
            watchdog.cancel()
            ok = won and problem is None
            record_problem = record("done" if ok else "failed", result if ok else None)
            self._release(run)
            if won:
                if ok and result is not None and record_problem is None:
                    run.finish("done", result=result)
                    run.emit("answer", result)
                    run.emit("done", {"status": str(result.get("status"))})
                else:
                    self._publish_failed(run, record_problem or problem or _problem(500, "internal_error", "no result"))

        def completed(future: Future) -> None:
            watchdog.cancel()
            if future.cancelled():
                won = run.claim()
                record("failed", None)
                self._release(run)
                if won:
                    self._publish_failed(run, _problem(503, "shutdown", "the queued run was cancelled"))
            elif future.exception() is not None:
                # Observe unexpected executor failures too: never strand a run or silently lose a Future.
                log.error("run %s: executor failed", run.id, exc_info=future.exception())
                self._release(run)
                self._publish_failed(run, _problem(500, "internal_error", "the executor failed"))
            with self._lock:
                self._inflight.pop(run.id, None)
                self._occupied.discard(run.id)

        try:
            with self._lock:
                future = self.pool.submit(body)
                self._inflight[run.id] = future
                watchdog.start()
        except RuntimeError:
            self._release(run)
            with self._lock:
                self._occupied.discard(run.id)
            run.claim()
            self._publish_failed(run, _problem(503, "shutdown", "the API is shutting down"))
            return run
        future.add_done_callback(completed)
        return run

    @staticmethod
    def _publish_failed(run: Run, problem: dict) -> None:
        if run.finish("failed", error=problem):
            run.emit("failed", problem)

    def _timeout(self, run: Run) -> None:
        """Said at once (the client is not kept waiting); the thread finishes in the background, its `claim` fails,
        so its `on_finish` records "failed" and its result is dropped."""
        if run.claim():
            self._publish_failed(run, _problem(504, "timeout", f"no answer within {TIMEOUT_S.get(run.kind, 120)} s; "
                                                               "the thread keeps what it did"))
            with self._lock:
                future = self._inflight.get(run.id)
            if future is not None:
                future.cancel()                 # queued work stops; a running worker retains capacity until exit

    def _release(self, run: Run) -> None:
        with self._lock:
            if run.id in self._released:
                return
            self._released.add(run.id)
            if run.conversation_id:
                self._busy_conversations.discard(run.conversation_id)
            if run.thread_id:
                self._reserved_threads.discard(run.thread_id)

    def get(self, run_id: str, owner: int) -> Run:
        run = self.runs.get(run_id)
        if run is None or run.owner != owner:
            raise ApiError(404, "no such run", slug="not_found")
        return run

    def _sweep(self) -> None:
        now = datetime.now(timezone.utc)
        for rid in [rid for rid, r in self.runs.items()
                    if rid not in self._occupied and r.finished_at
                    and (now - r.finished_at).total_seconds() > KEEP_FINISHED_S]:
            del self.runs[rid]
            self._released.discard(rid)

    def shutdown(self) -> None:
        with self._lock:
            self._closed = True
        self.pool.shutdown(wait=False, cancel_futures=True)


def failure(exc: BaseException, **tags) -> tuple[int, str, str]:
    """(status, slug, detail) of an exception inside a run — the same mapping as `errors.register` for a request;
    an unexpected one goes to Sentry with the run's tags (its thread id = the LangSmith trace's, ADR-062)."""
    from psycopg_pool import PoolTimeout

    from pipelines.agents import llm, monitoring
    if isinstance(exc, llm.Exhausted):
        return 503, "quota", "the free model quota is spent for now; try again later"
    if isinstance(exc, (psycopg.OperationalError, PoolTimeout)):
        return 503, "database", "a database is not reachable"
    if isinstance(exc, ValueError):
        return 422, "invalid_request", "the request cannot be answered as given"
    monitoring.capture(exc, **tags)
    return 500, "internal_error", "something went wrong; quote the run id"


@contextmanager
def thread_lock(thread_id: str) -> Iterator[None]:
    """C5: one run per graph thread across processes. A session advisory lock on a connection of its own (not the
    pool's: a run holds it for minutes); taken without waiting — a busy thread is a 409, not a queue."""
    try:
        with locks.thread_lock(thread_id):
            yield
    except locks.ThreadBusy as exc:
        raise ApiError(409, str(exc), slug="thread_busy") from None
