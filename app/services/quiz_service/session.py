"""
In-memory quiz session store.

Sessions expire automatically after TTL_SECONDS.  No DB writes; quizzes
disappear when the session ends or the server restarts — by design.
"""
import time
import uuid
from dataclasses import dataclass, field

TTL_SECONDS = 7200  # 2 hours


@dataclass
class _StoredQuestion:
    id: int
    question: str
    options: dict[str, str]   # {"A": ..., "B": ..., "C": ..., "D": ...}
    correct: str              # "A" | "B" | "C" | "D"
    explanation: str


@dataclass
class _Session:
    file_id: int
    questions: list[_StoredQuestion]
    created_at: float = field(default_factory=time.monotonic)

    def is_expired(self) -> bool:
        return time.monotonic() - self.created_at > TTL_SECONDS


_store: dict[str, _Session] = {}


def create_session(file_id: int, questions: list[_StoredQuestion]) -> str:
    _evict_expired()
    session_id = str(uuid.uuid4())
    _store[session_id] = _Session(file_id=file_id, questions=questions)
    return session_id


def get_question(session_id: str, question_id: int) -> _StoredQuestion | None:
    session = _store.get(session_id)
    if session is None or session.is_expired():
        _store.pop(session_id, None)
        return None
    return next((q for q in session.questions if q.id == question_id), None)


def get_session(session_id: str) -> _Session | None:
    session = _store.get(session_id)
    if session is None or session.is_expired():
        _store.pop(session_id, None)
        return None
    return session


def _evict_expired() -> None:
    expired = [sid for sid, s in _store.items() if s.is_expired()]
    for sid in expired:
        del _store[sid]
