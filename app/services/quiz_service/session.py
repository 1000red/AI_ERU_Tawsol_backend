import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

SECONDS = 7200  # 2 hours


@dataclass
class _StoredQuestion:
    id: int
    question: str
    options: dict[str, str]   # {"A": ..., "B": ..., "C": ..., "D": ...}
    correct: str              # "A" | "B" | "C" | "D"
    explanation: str
    reference_quote: str = "" # Verbatim citation from uploaded lecture material
    question_type: str = "mcq" # "mcq" | "true_false" | "matching" | "short_answer"
    bloom_level: str = "comprehension" # "recall" | "comprehension" | "application" | "analysis"


@dataclass
class _Session:
    file_id: int
    questions: list[_StoredQuestion]
    created_at: float = field(default_factory=time.monotonic)

    def is_expired(self) -> bool:
        return time.monotonic() - self.created_at > SECONDS


_store: dict[str, _Session] = {}
_sessions = _store  # Alias for backward compatibility


def _evict_expired() -> None:
    expired = [sid for sid, s in _store.items() if s.is_expired()]
    for sid in expired:
        del _store[sid]


def create_session(file_id: int, questions: list[_StoredQuestion]) -> str:
    _evict_expired()
    session_id = str(uuid.uuid4())
    _store[session_id] = _Session(file_id=file_id, questions=questions)
    return session_id


def get_session(session_id: str) -> Optional[_Session]:
    _evict_expired()
    session = _store.get(session_id)
    if session is None or session.is_expired():
        _store.pop(session_id, None)
        return None
    return session


def get_question(session_id: str, question_id: int) -> Optional[_StoredQuestion]:
    session = get_session(session_id)
    if not session:
        return None
    return next((q for q in session.questions if q.id == question_id), None)


def update_session_questions(session_id: str, new_questions: list[_StoredQuestion]) -> bool:
    session = get_session(session_id)
    if not session:
        return False
    session.questions = new_questions
    return True


def replace_session_question(session_id: str, question_id: int, new_q: _StoredQuestion) -> bool:
    session = get_session(session_id)
    if not session:
        return False
    for idx, q in enumerate(session.questions):
        if q.id == question_id:
            session.questions[idx] = new_q
            return True
    return False
