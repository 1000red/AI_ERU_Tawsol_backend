import json
import os
import shutil
import uuid
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from app.db.database import get_db, SessionLocal
from app.core.security import get_current_user_id, get_current_user_id_ws
from app.schemas.chat import MessageSend, MessageEdit, MessageOut, ConversationOut, ConversationUserOut
from app.services.chat_service import (
    ws_manager,
    save_message,
    edit_message,
    delete_message,
    get_conversation,
    get_user_conversations,
    search_users,
    can_chat,
    mark_messages_delivered,
    mark_messages_seen,
    pin_conversation,
    unpin_conversation,
    update_last_seen,
)

router = APIRouter(prefix="/chat", tags=["Chat"])

VOICE_DIR = "uploads/voice"
ALLOWED_AUDIO_EXTENSIONS = {".m4a", ".mp3", ".ogg", ".wav", ".aac", ".webm", ".opus", ".flac"}
MAX_VOICE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

FILE_DIR = "uploads/files"
ALLOWED_FILE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv",
    ".mp3", ".m4a", ".ogg", ".wav", ".aac",
    ".zip", ".rar",
}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


# ── REST endpoints ────────────────────────────────────────────────────────────

@router.post("/upload/voice", status_code=status.HTTP_201_CREATED)
async def upload_voice(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format. Allowed: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}",
        )

    contents = await file.read()
    if len(contents) > MAX_VOICE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Voice file exceeds 25 MB limit")

    filename = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(VOICE_DIR, filename)
    with open(save_path, "wb") as f:
        f.write(contents)

    return {
        "file_url":        f"/uploads/voice/{filename}",
        "file_name":       file.filename,
        "file_size_bytes": len(contents),
    }


@router.post("/upload/file", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_FILE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_FILE_EXTENSIONS))}",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit.")

    os.makedirs(FILE_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(FILE_DIR, filename)
    with open(save_path, "wb") as f:
        f.write(contents)

    return {
        "file_url":        f"/uploads/files/{filename}",
        "file_name":       file.filename,
        "file_size_bytes": len(contents),
    }


@router.post("/send", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def send_message(
    data: MessageSend,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return save_message(
        db,
        sender_id=user_id,
        receiver_id=data.receiver_id,
        content_type=data.content_type,
        message=data.message,
        file_url=data.file_url,
        file_name=data.file_name,
        file_size_bytes=data.file_size_bytes,
        voice_duration_seconds=data.voice_duration_seconds,
        reply_to_id=data.reply_to_id,
    )


@router.get("/history/{user1_id}/{user2_id}", response_model=list[MessageOut])
def get_history(
    user1_id: int,
    user2_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    if user_id not in (user1_id, user2_id):
        raise HTTPException(status_code=403, detail="Access denied")
    return get_conversation(db, user1_id, user2_id)


@router.get("/conversations", response_model=list[ConversationOut])
def my_conversations(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return get_user_conversations(db, user_id)


@router.get("/search", response_model=list[ConversationUserOut])
def search(
    q: str = Query(..., min_length=1),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    users = search_users(db, q, user_id)
    return [
        ConversationUserOut(
            id=u.user_id,
            name=u.name,
            type_code=u.type_code,
            is_online=ws_manager.is_online(u.user_id),
            last_seen=u.last_seen,
            student_id=u.uni_code if u.type_code == "STU" else None,
        )
        for u in users
    ]


@router.put("/message/{chat_id}", response_model=MessageOut)
async def update_message(
    chat_id: int,
    data: MessageEdit,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    msg = edit_message(db, chat_id, data.message, user_id)
    other_id = msg.receiver_id if msg.sender_id == user_id else msg.sender_id
    await ws_manager.send_to_user(other_id, {
        "type":      "message_edited",
        "chat_id":   msg.chat_id,
        "message":   msg.message,
        "edited_at": msg.edited_at.isoformat(),
    })
    return msg


@router.delete("/message/{chat_id}", response_model=MessageOut)
async def remove_message(
    chat_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    msg = delete_message(db, chat_id, user_id)
    other_id = msg.receiver_id if msg.sender_id == user_id else msg.sender_id
    await ws_manager.send_to_user(other_id, {
        "type":    "message_deleted",
        "chat_id": msg.chat_id,
    })
    return msg


@router.get("/online")
def online_users():
    return {"online_users": ws_manager.online_users()}


@router.get("/online/{user_id}")
def is_online(user_id: int):
    return {"user_id": user_id, "online": ws_manager.is_online(user_id)}


@router.put("/seen/{other_user_id}", status_code=status.HTTP_204_NO_CONTENT)
def mark_seen(
    other_user_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    mark_messages_seen(db, receiver_id=user_id, sender_id=other_user_id)


@router.post("/pin/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
def pin(
    partner_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    pin_conversation(db, user_id=user_id, partner_id=partner_id)


@router.delete("/pin/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
def unpin(
    partner_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    unpin_conversation(db, user_id=user_id, partner_id=partner_id)


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws/{user_id}")
async def websocket_chat(
    websocket: WebSocket,
    user_id: int,
    token: str = Query(...),
):
    # Must accept() before any close() — otherwise Starlette returns 403 HTTP
    await websocket.accept()

    try:
        token_user_id = get_current_user_id_ws(token)
        if token_user_id != user_id:
            await websocket.close(code=4001, reason="Unauthorized")
            return
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    ws_manager.connect(user_id, websocket)

    db: Session = SessionLocal()
    try:
        affected_senders = mark_messages_delivered(db, receiver_id=user_id)
        for sender_id in affected_senders:
            await ws_manager.send_to_user(sender_id, {
                "type":        "delivered",
                "receiver_id": user_id,
            })

        await ws_manager.send_to_user(user_id, {
            "type":         "connected",
            "user_id":      user_id,
            "online_users": ws_manager.online_users(),
        })

        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
                continue
            msg_type = data.get("type", "message")

            if msg_type == "message":
                receiver_id  = int(data["receiver_id"])
                content_type = data.get("content_type", "text")
                text         = data.get("message") or None

                if not text and content_type == "text":
                    continue

                try:
                    chat = save_message(
                        db,
                        sender_id=user_id,
                        receiver_id=receiver_id,
                        content_type=content_type,
                        message=text,
                        file_url=data.get("file_url"),
                        file_name=data.get("file_name"),
                        file_size_bytes=data.get("file_size_bytes"),
                        voice_duration_seconds=data.get("voice_duration_seconds"),
                        reply_to_id=data.get("reply_to_id"),
                    )
                except HTTPException as e:
                    db.rollback()
                    await ws_manager.send_to_user(user_id, {"type": "error", "detail": e.detail})
                    continue
                except Exception:
                    db.rollback()
                    await ws_manager.send_to_user(user_id, {"type": "error", "detail": "Failed to send message"})
                    continue

                replied_payload = None
                if chat.reply_to_id:
                    r = chat.reply_to
                    if r:
                        replied_payload = {
                            "chat_id":      r.chat_id,
                            "sender_id":    r.sender_id,
                            "content_type": r.content_type,
                            "message":      r.message if not r.is_deleted else None,
                            "file_name":    r.file_name,
                            "is_deleted":   r.is_deleted,
                        }

                payload = {
                    "type":                   "message",
                    "chat_id":                chat.chat_id,
                    "sender_id":              user_id,
                    "receiver_id":            receiver_id,
                    "content_type":           chat.content_type,
                    "message":                chat.message,
                    "file_url":               chat.file_url,
                    "file_name":              chat.file_name,
                    "file_size_bytes":        chat.file_size_bytes,
                    "voice_duration_seconds": chat.voice_duration_seconds,
                    "status":                 chat.status,
                    "sent_at":                chat.sent_at.isoformat(),
                    "reply_to_id":            chat.reply_to_id,
                    "reply_to":               replied_payload,
                }
                await ws_manager.send_to_user(receiver_id, payload)
                await ws_manager.send_to_user(user_id, {**payload, "type": "sent"})

            elif msg_type == "seen":
                sender_id = data.get("sender_id")
                if sender_id:
                    sender_id = int(sender_id)
                    mark_messages_seen(db, receiver_id=user_id, sender_id=sender_id)
                    await ws_manager.send_to_user(sender_id, {
                        "type":        "seen",
                        "receiver_id": user_id,
                    })

            elif msg_type == "typing":
                receiver_id = int(data["receiver_id"])
                await ws_manager.send_to_user(receiver_id, {
                    "type":      "typing",
                    "sender_id": user_id,
                    "is_typing": data.get("is_typing", True),
                })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] Error user {user_id}: {e}")
    finally:
        ws_manager.disconnect(user_id, websocket)
        update_last_seen(db, user_id)
        db.close()
