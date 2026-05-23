from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import WebSocket, HTTPException
from datetime import datetime
from typing import Optional

from app.models.chat import ChatHistory
from app.models.user import User


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


# ── Chat permissions ──────────────────────────────────────────────────────────

def can_chat(db: Session, sender_id: int, receiver_id: int) -> bool:
    from app.models.material import MaterialStudent, MaterialTeacher

    sender   = db.query(User).filter(User.user_id == sender_id).first()
    receiver = db.query(User).filter(User.user_id == receiver_id).first()

    if not sender or not receiver:
        return False

    # ADM can talk to anyone, and anyone can talk to ADM
    if "ADM" in (sender.type_code, receiver.type_code):
        return True

    staff_types = {"DR", "TA", "PROF"}

    # staff ↔ staff: allowed only if they co-teach a material
    if sender.type_code in staff_types and receiver.type_code in staff_types:
        sender_materials = db.query(MaterialTeacher.material_id).filter(
            MaterialTeacher.user_id == sender_id
        ).subquery()
        shared = db.query(MaterialTeacher).filter(
            MaterialTeacher.user_id == receiver_id,
            MaterialTeacher.material_id.in_(sender_materials),
        ).first()
        return shared is not None

    # STU ↔ DR/TA: allowed only if they share a material
    if sender.type_code == "STU" and receiver.type_code in staff_types:
        student_id, teacher_id = sender_id, receiver_id
    elif sender.type_code in staff_types and receiver.type_code == "STU":
        student_id, teacher_id = receiver_id, sender_id
    else:
        return False  # STU ↔ STU

    student_materials = db.query(MaterialStudent.material_id).filter(
        MaterialStudent.user_id == student_id
    ).subquery()

    shared = db.query(MaterialTeacher).filter(
        MaterialTeacher.user_id == teacher_id,
        MaterialTeacher.material_id.in_(student_materials),
    ).first()

    return shared is not None


# ── Chat CRUD ─────────────────────────────────────────────────────────────────

def save_message(
    db: Session,
    sender_id: int,
    receiver_id: int,
    message: Optional[str] = None,
    message_type: str = "text",
    file_url: Optional[str] = None,
    file_name: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
    voice_duration_seconds: Optional[int] = None,
) -> ChatHistory:
    if not can_chat(db, sender_id, receiver_id):
        raise HTTPException(status_code=403, detail="You are not allowed to chat with this user")

    chat = ChatHistory(
        sender_id=sender_id,
        receiver_id=receiver_id,
        message=message,
        message_type=message_type,
        file_url=file_url,
        file_name=file_name,
        file_size_bytes=file_size_bytes,
        voice_duration_seconds=voice_duration_seconds,
        status="sent",
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


def get_user_conversations(db: Session, user_id: int) -> list[dict]:
    """Return one conversation object per partner, ordered by most recent message."""
    from sqlalchemy import func, or_
    from app.models.user import User

    # Subquery: latest chat_id per (sender, receiver) pair involving user_id
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

    latest_messages = (
        db.query(ChatHistory)
        .join(subq, ChatHistory.chat_id == subq.c.latest_id)
        .order_by(ChatHistory.sent_at.desc())
        .all()
    )

    conversations = []
    for msg in latest_messages:
        other_id = msg.receiver_id if msg.sender_id == user_id else msg.sender_id
        other_user = db.query(User).filter(User.user_id == other_id).first()
        if not other_user:
            continue

        # Count messages sent TO user_id by this partner that are not yet seen
        unread_count = (
            db.query(ChatHistory)
            .filter(
                ChatHistory.sender_id == other_id,
                ChatHistory.receiver_id == user_id,
                ChatHistory.status != "seen",
            )
            .count()
        )

        conversations.append({
            "other_user": {
                "id":              other_user.user_id,
                "name":            other_user.name,
                "profile_picture": other_user.profile_picture,
                "type_code":       other_user.type_code,
                "is_online":       ws_manager.is_online(other_id),
            },
            "last_message": msg,
            "unread_count": unread_count,
        })

    return conversations


def search_users(db: Session, query: str, current_user_id: int) -> list[User]:
    q = query.strip()
    filters = []
    if q.isdigit():
        filters.append(User.user_id == int(q))
    filters.append(User.name.ilike(f"%{q}%"))
    return (
        db.query(User)
        .filter(User.user_id != current_user_id)
        .filter(or_(*filters) if len(filters) > 1 else filters[0])
        .limit(20)
        .all()
    )
