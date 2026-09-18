from dataclasses import dataclass
from time import time


@dataclass
class LiveSession:
    session_id: str
    user_id: str
    worker_id: str | None = None
    created_at: float = 0.0


class InMemorySessionStore:
    def __init__(self) -> None:
        self._items: dict[str, LiveSession] = {}

    def create(self, session_id: str, user_id: str) -> LiveSession:
        session = LiveSession(session_id, user_id, created_at=time())
        self._items[session_id] = session
        return session

    def get(self, session_id: str) -> LiveSession | None:
        return self._items.get(session_id)

    def delete(self, session_id: str) -> None:
        self._items.pop(session_id, None)
