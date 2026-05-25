from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from fastapi import WebSocket, HTTPException
from datetime import datetime, timezone
from typing import Optional

from app.models.chat import ChatHistory, PinnedConversation
from app.models.user import User


# ── WebSocket Connection Manager ──────────────────────────────────────────────

class ConnectionManager:
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


ws_manager = ConnectionManager()


# ── Chat permissions ──────────────────────────────────────────────────────────

def can_chat(db: Session, sender_id: int, receiver_id: int) -> bool:
    from app.models.material import MaterialStudent, MaterialTeacher

    sender   = db.query(User).filter(User.user_id == sender_id).first()
    receiver = db.query(User).filter(User.user_id == receiver_id).first()

    if not sender or not receiver:
        return False

    # ADM talks to everyone
    if "ADM" in (sender.type_code, receiver.type_code):
        return True

    dr_types  = {"DR", "PROF"}
    all_staff = {"DR", "PROF", "TA"}

    # DR ↔ DR — always allowed
    if sender.type_code in dr_types and receiver.type_code in dr_types:
        return True

    # STU ↔ STU — never allowed
    if sender.type_code == "STU" and receiver.type_code == "STU":
        return False

    # For all remaining pairs (DR↔TA, TA↔TA, STU↔DR, STU↔TA)
    # require a shared material
    if sender.type_code == "STU":
        student_id = sender_id
        staff_id   = receiver_id
    elif receiver.type_code == "STU":
        student_id = receiver_id
        staff_id   = sender_id
    else:
        # both staff (DR↔TA or TA↔TA) — require co-teaching same material
        sender_materials = db.query(MaterialTeacher.material_id).filter(
            MaterialTeacher.user_id == sender_id
        )
        return db.query(MaterialTeacher).filter(
            MaterialTeacher.user_id == receiver_id,
            MaterialTeacher.material_id.in_(sender_materials),
        ).first() is not None

    # STU ↔ staff: student must be enrolled in a material the staff member teaches
    student_materials = db.query(MaterialStudent.material_id).filter(
        MaterialStudent.user_id == student_id
    )
    return db.query(MaterialTeacher).filter(
        MaterialTeacher.user_id == staff_id,
        MaterialTeacher.material_id.in_(student_materials),
    ).first() is not None


# ── Chat CRUD ─────────────────────────────────────────────────────────────────

def save_message(
    db: Session,
    sender_id: int,
    receiver_id: int,
    content_type: str = "text",
    message: Optional[str] = None,
    file_url: Optional[str] = None,
    file_name: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
    voice_duration_seconds: Optional[int] = None,
) -> ChatHistory:
    if sender_id == receiver_id:
        raise HTTPException(status_code=400, detail="Cannot send a message to yourself")

    if not can_chat(db, sender_id, receiver_id):
        raise HTTPException(status_code=403, detail="You are not allowed to chat with this user")

    initial_status = "delivered" if ws_manager.is_online(receiver_id) else "sent"

    chat = ChatHistory(
        sender_id=sender_id,
        receiver_id=receiver_id,
        content_type=content_type,
        message=message,
        file_url=file_url,
        file_name=file_name,
        file_size_bytes=file_size_bytes,
        voice_duration_seconds=voice_duration_seconds,
        status=initial_status,
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
            or_(
                and_(ChatHistory.sender_id == user1_id,   ChatHistory.receiver_id == user2_id),
                and_(ChatHistory.sender_id == user2_id,   ChatHistory.receiver_id == user1_id),
            )
        )
        .order_by(ChatHistory.sent_at)
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_user_conversations(db: Session, user_id: int) -> list[dict]:
    from sqlalchemy import func

    subq = (
        db.query(
            func.greatest(ChatHistory.sender_id, ChatHistory.receiver_id).label("u1"),
            func.least(ChatHistory.sender_id,    ChatHistory.receiver_id).label("u2"),
            func.max(ChatHistory.chat_id).label("latest_id"),
        )
        .filter(or_(ChatHistory.sender_id == user_id, ChatHistory.receiver_id == user_id))
        .group_by("u1", "u2")
        .subquery()
    )

    latest_messages = (
        db.query(ChatHistory)
        .join(subq, ChatHistory.chat_id == subq.c.latest_id)
        .order_by(ChatHistory.sent_at.desc())
        .all()
    )

    pinned_partners = {
        row.partner_id
        for row in db.query(PinnedConversation.partner_id)
        .filter(PinnedConversation.user_id == user_id)
        .all()
    }

    conversations = []
    for msg in latest_messages:
        other_id   = msg.receiver_id if msg.sender_id == user_id else msg.sender_id
        other_user = db.query(User).filter(User.user_id == other_id).first()
        if not other_user:
            continue

        unread_count = (
            db.query(ChatHistory)
            .filter(
                ChatHistory.sender_id == other_id,
                ChatHistory.receiver_id == user_id,
                ChatHistory.status != "seen",
            )
            .count()
        )

        min_id = min(user_id, other_id)
        max_id = max(user_id, other_id)

        conversations.append({
            "id": f"{min_id}_{max_id}",
            "other_user": {
                "id":              other_user.user_id,
                "name":            other_user.name,
                "profile_picture": other_user.profile_picture,
                "type_code":       other_user.type_code,
                "is_online":       ws_manager.is_online(other_id),
                "last_seen":       other_user.last_seen,
                "student_id":      other_user.uni_code,
            },
            "last_message": msg,
            "unread_count": unread_count,
            "is_pinned":    other_id in pinned_partners,
        })

    conversations.sort(key=lambda c: (not c["is_pinned"], 0))
    return conversations


def mark_messages_delivered(db: Session, receiver_id: int, sender_id: Optional[int] = None) -> list[int]:
    q = db.query(ChatHistory).filter(
        ChatHistory.receiver_id == receiver_id,
        ChatHistory.status == "sent",
    )
    if sender_id is not None:
        q = q.filter(ChatHistory.sender_id == sender_id)

    messages = q.all()
    affected_senders = set()
    for msg in messages:
        msg.status = "delivered"
        affected_senders.add(msg.sender_id)
    db.commit()
    return list(affected_senders)


def mark_messages_seen(db: Session, receiver_id: int, sender_id: int) -> bool:
    updated = (
        db.query(ChatHistory)
        .filter(
            ChatHistory.receiver_id == receiver_id,
            ChatHistory.sender_id == sender_id,
            ChatHistory.status != "seen",
        )
        .all()
    )
    for msg in updated:
        msg.status = "seen"
    db.commit()
    return len(updated) > 0


EDIT_DELETE_WINDOW_MINUTES = 15


def edit_message(db: Session, chat_id: int, new_text: str, user_id: int) -> ChatHistory:
    msg = db.query(ChatHistory).filter(ChatHistory.chat_id == chat_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.sender_id != user_id:
        raise HTTPException(status_code=403, detail="You can only edit your own messages")
    if msg.is_deleted:
        raise HTTPException(status_code=400, detail="Cannot edit a deleted message")
    if msg.content_type != "text":
        raise HTTPException(status_code=400, detail="Only text messages can be edited")

    elapsed = (datetime.now(timezone.utc) - msg.sent_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
    if elapsed > EDIT_DELETE_WINDOW_MINUTES:
        raise HTTPException(status_code=403, detail=f"Cannot edit after {EDIT_DELETE_WINDOW_MINUTES} minutes")

    msg.message   = new_text
    msg.edited_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(msg)
    return msg


def delete_message(db: Session, chat_id: int, user_id: int) -> ChatHistory:
    msg = db.query(ChatHistory).filter(ChatHistory.chat_id == chat_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.sender_id != user_id:
        raise HTTPException(status_code=403, detail="You can only delete your own messages")
    if msg.is_deleted:
        raise HTTPException(status_code=400, detail="Message already deleted")

    elapsed = (datetime.now(timezone.utc) - msg.sent_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
    if elapsed > EDIT_DELETE_WINDOW_MINUTES:
        raise HTTPException(status_code=403, detail=f"Cannot delete after {EDIT_DELETE_WINDOW_MINUTES} minutes")

    msg.is_deleted = True
    msg.message    = None
    msg.file_url   = None
    msg.file_name  = None
    db.commit()
    db.refresh(msg)
    return msg


def pin_conversation(db: Session, user_id: int, partner_id: int) -> None:
    existing = db.query(PinnedConversation).filter(
        PinnedConversation.user_id == user_id,
        PinnedConversation.partner_id == partner_id,
    ).first()
    if not existing:
        db.add(PinnedConversation(user_id=user_id, partner_id=partner_id))
        db.commit()


def unpin_conversation(db: Session, user_id: int, partner_id: int) -> None:
    db.query(PinnedConversation).filter(
        PinnedConversation.user_id == user_id,
        PinnedConversation.partner_id == partner_id,
    ).delete()
    db.commit()


def update_last_seen(db: Session, user_id: int) -> None:
    user = db.query(User).filter(User.user_id == user_id).first()
    if user:
        user.last_seen = datetime.now(timezone.utc)
        db.commit()


def search_users(db: Session, query: str, current_user_id: int) -> list[User]:
    from app.models.material import MaterialStudent, MaterialTeacher

    q           = query.strip()
    current     = db.query(User).filter(User.user_id == current_user_id).first()
    if not current:
        return []

    dr_types    = {"DR", "PROF"}
    all_staff   = {"DR", "PROF", "TA"}

    # ── Build permission filter (who this user is allowed to chat with) ──────
    if current.type_code == "ADM":
        permission_filter = User.user_id != current_user_id

    elif current.type_code == "STU":
        # Student → only teachers of materials they're enrolled in + ADMs
        enrolled = db.query(MaterialStudent.material_id).filter(
            MaterialStudent.user_id == current_user_id
        )
        allowed_teacher_ids = db.query(MaterialTeacher.user_id).filter(
            MaterialTeacher.material_id.in_(enrolled)
        )
        permission_filter = or_(
            User.user_id.in_(allowed_teacher_ids),
            User.type_code == "ADM",
        )

    elif current.type_code in dr_types:
        # DR → all other DRs + TA/STU sharing a material + ADMs
        my_materials = db.query(MaterialTeacher.material_id).filter(
            MaterialTeacher.user_id == current_user_id
        )
        shared_staff_ids = db.query(MaterialTeacher.user_id).filter(
            MaterialTeacher.material_id.in_(my_materials),
            MaterialTeacher.user_id != current_user_id,
        )
        shared_student_ids = db.query(MaterialStudent.user_id).filter(
            MaterialStudent.material_id.in_(my_materials)
        )
        permission_filter = or_(
            User.type_code.in_(list(dr_types)),        # all DRs
            User.user_id.in_(shared_staff_ids),        # TAs sharing a material
            User.user_id.in_(shared_student_ids),      # students sharing a material
            User.type_code == "ADM",
        )

    else:  # TA
        # TA → DR/TA/STU sharing a material + ADMs
        my_materials = db.query(MaterialTeacher.material_id).filter(
            MaterialTeacher.user_id == current_user_id
        )
        shared_staff_ids = db.query(MaterialTeacher.user_id).filter(
            MaterialTeacher.material_id.in_(my_materials),
            MaterialTeacher.user_id != current_user_id,
        )
        shared_student_ids = db.query(MaterialStudent.user_id).filter(
            MaterialStudent.material_id.in_(my_materials)
        )
        permission_filter = or_(
            User.user_id.in_(shared_staff_ids),
            User.user_id.in_(shared_student_ids),
            User.type_code == "ADM",
        )

    # ── Build search filter ───────────────────────────────────────────────────
    # Students can be found by name OR ID; DR/TA/ADM by name only
    name_filter = User.name.ilike(f"%{q}%")

    if q.isdigit():
        # ID search only matches student records
        id_filter = and_(
            User.type_code == "STU",
            or_(User.user_id == int(q), User.uni_code == q),
        )
        search_filter = or_(name_filter, id_filter)
    else:
        search_filter = name_filter

    return (
        db.query(User)
        .filter(User.user_id != current_user_id)
        .filter(permission_filter)
        .filter(search_filter)
        .limit(20)
        .all()
    )
