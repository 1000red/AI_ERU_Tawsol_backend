from sqlalchemy.orm import Session
from fastapi import WebSocket
from datetime import datetime

from app.models.chat import ChatHistory
# from app.schemas.chat import MessageSend


# ── WebSocket Connection Manager ──────────────────────────────────────────────

class ConnectionManager:
    """Manages active WebSocket connections, keyed by user_id."""

    def __init__(self):
        self.active: dict[int, list[WebSocket]] = {}

    async def connect(self, user_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self.active.setdefault(user_id, []).append(ws)

    def disconnect(self, user_id: int, ws: WebSocket) -> None:
        conns = self.active.get(user_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self.active.pop(user_id, None)

    async def send_to_user(self, user_id: int, payload: dict) -> None:
        for ws in list(self.active.get(user_id, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                pass

    def is_online(self, user_id: int) -> bool:
        return bool(self.active.get(user_id))

    def online_users(self) -> list[int]:
        return list(self.active.keys())


# Singleton — shared across all WebSocket connections
ws_manager = ConnectionManager()


# ── Chat CRUD ─────────────────────────────────────────────────────────────────

def save_message(db: Session, sender_id: int, receiver_id: int, message: str) -> ChatHistory:
    chat = ChatHistory(
        sender_id=sender_id,
        receiver_id=receiver_id,
        message=message,
        sent_at=datetime.utcnow(),
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


def get_conversation(
    db: Session,
    user1_id: int,
    user2_id: int,
    skip: int = 0,
    limit: int = 50,
) -> list[ChatHistory]:
    return (
        db.query(ChatHistory)
        .filter(
            (
                (ChatHistory.sender_id == user1_id) &
                (ChatHistory.receiver_id == user2_id)
            ) | (
                (ChatHistory.sender_id == user2_id) &
                (ChatHistory.receiver_id == user1_id)
            )
        )
        .order_by(ChatHistory.sent_at)
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_user_conversations(db: Session, user_id: int) -> list[ChatHistory]:
    """Return the latest message per conversation partner."""
    from sqlalchemy import func, or_, and_
    subq = (
        db.query(
            func.greatest(ChatHistory.sender_id, ChatHistory.receiver_id).label("u1"),
            func.least(ChatHistory.sender_id, ChatHistory.receiver_id).label("u2"),
            func.max(ChatHistory.chat_id).label("latest_id"),
        )
        .filter(
            or_(
                ChatHistory.sender_id == user_id,
                ChatHistory.receiver_id == user_id,
            )
        )
        .group_by("u1", "u2")
        .subquery()
    )
    return (
        db.query(ChatHistory)
        .join(subq, ChatHistory.chat_id == subq.c.latest_id)
        .order_by(ChatHistory.sent_at.desc())
        .all()
    )
