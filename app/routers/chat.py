import json
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.database import get_db, SessionLocal
from app.core.security import get_current_user_id, get_current_user_id_ws
from app.schemas.chat import MessageSend, MessageOut, ConversationOut
from app.services.chat_service import ws_manager, save_message, get_conversation, get_user_conversations, search_users, can_chat

router = APIRouter(prefix="/chat", tags=["Chat"])


# ── REST endpoints ────────────────────────────────────────────────────────────

@router.post("/send", response_model=MessageOut, status_code=201)
def send_message(
    data: MessageSend,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return save_message(
        db,
        sender_id=user_id,
        receiver_id=data.receiver_id,
        message=data.message,
        message_type=data.message_type,
        file_url=data.file_url,
        file_name=data.file_name,
        file_size_bytes=data.file_size_bytes,
        voice_duration_seconds=data.voice_duration_seconds,
    )


@router.get("/history/{user1_id}/{user2_id}", response_model=list[MessageOut])
def get_history(
    user1_id: int,
    user2_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    return get_conversation(db, user1_id, user2_id, skip, limit)


@router.get("/conversations", response_model=list[ConversationOut])
def my_conversations(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return get_user_conversations(db, user_id)


@router.get("/search")
def search(
    q: str = Query(..., min_length=1),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return search_users(db, q, user_id)


@router.get("/online")
def online_users():
    return {"online_users": ws_manager.online_users()}


@router.get("/online/{user_id}")
def is_online(user_id: int):
    return {"user_id": user_id, "online": ws_manager.is_online(user_id)}


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws/{user_id}")
async def websocket_chat(
    websocket: WebSocket,
    user_id: int,
    token: str = Query(...),
):
    # Authenticate
    try:
        token_user_id = get_current_user_id_ws(token)
        if token_user_id != user_id:
            await websocket.close(code=4001, reason="Unauthorized")
            return
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await ws_manager.connect(user_id, websocket)
    await ws_manager.send_to_user(user_id, {
        "type": "connected",
        "user_id": user_id,
        "online_users": ws_manager.online_users(),
    })

    db: Session = SessionLocal()
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type", "message")

            if msg_type == "message":
                receiver_id = int(data["receiver_id"])
                text = data.get("message") or None
                media_type = data.get("message_type", "text")

                # Require either text or a media file
                if not text and media_type == "text":
                    continue

                try:
                    chat = save_message(
                        db,
                        sender_id=user_id,
                        receiver_id=receiver_id,
                        message=text,
                        message_type=media_type,
                        file_url=data.get("file_url"),
                        file_name=data.get("file_name"),
                        file_size_bytes=data.get("file_size_bytes"),
                        voice_duration_seconds=data.get("voice_duration_seconds"),
                    )
                except HTTPException as e:
                    await ws_manager.send_to_user(user_id, {"type": "error", "detail": e.detail})
                    continue
                payload = {
                    "type":                  "message",
                    "chat_id":               chat.chat_id,
                    "sender_id":             user_id,
                    "receiver_id":           receiver_id,
                    "message":               chat.message,
                    "message_type":          chat.message_type,
                    "file_url":              chat.file_url,
                    "file_name":             chat.file_name,
                    "file_size_bytes":       chat.file_size_bytes,
                    "voice_duration_seconds": chat.voice_duration_seconds,
                    "status":                chat.status,
                    "sent_at":               chat.sent_at.isoformat(),
                }
                await ws_manager.send_to_user(receiver_id, payload)
                await ws_manager.send_to_user(user_id, {**payload, "type": "sent"})

            elif msg_type == "typing":
                receiver_id = int(data["receiver_id"])
                await ws_manager.send_to_user(receiver_id, {
                    "type": "typing",
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
        db.close()
