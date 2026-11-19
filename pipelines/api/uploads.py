"""The conversations' uploads in this API process (plan §3.3, ADR-043): one `session_store.Session` per conversation,
in memory only — gone when the conversation closes, after 8 h, or when the process restarts (the conversation row and
its question threads stay; its documents must be uploaded again). One process by design (plan §4, owner A2): a
second process would need them in Redis with a TTL (ADR-018 trigger).

The `SessionStore` (and the 2.2 GB local bge-m3 model it loads) is built at the first upload, not at start-up.
"""
import threading

from pipelines.lib import session_store


class UploadSessions:
    def __init__(self, store_factory=session_store.SessionStore):
        self._factory = store_factory
        self._store: session_store.SessionStore | None = None
        self._by_conversation: dict[str, str] = {}
        self._lock = threading.Lock()

    @property
    def store(self) -> session_store.SessionStore:
        with self._lock:
            if self._store is None:
                self._store = self._factory()
            return self._store

    def get(self, conversation_id: str, employee_id: int, *, create: bool) -> session_store.Session | None:
        """The conversation's session (its owner's only: `SessionStore.get` refuses anyone else), a new one when
        `create`, else None when it has none or it expired."""
        sid = self._by_conversation.get(conversation_id)
        if sid is not None and self._store is not None:
            try:
                return self._store.get(sid, employee_id)
            except session_store.SessionExpired:
                self._by_conversation.pop(conversation_id, None)
        if not create:
            return None
        s = self.store.open(employee_id)
        self._by_conversation[conversation_id] = s.session_id
        return s

    def close(self, conversation_id: str) -> None:
        sid = self._by_conversation.pop(conversation_id, None)
        if sid is not None and self._store is not None:
            self._store.close(sid)
