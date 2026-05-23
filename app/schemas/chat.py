from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime

from app.schemas.file_types.__types__ import FILE_TYPES


MESSAGE_TYPES = Literal["text", "image", "voice", "file"]


class MessageSend(BaseModel):
    receiver_id:            int
    message:                Optional[str]        = None
    message_type:           MESSAGE_TYPES        = "text"
    file_type:              Optional[FILE_TYPES] = None
    file_url:               Optional[str]        = None
    file_name:              Optional[str]        = None
    file_size_bytes:        Optional[int]        = None
    voice_duration_seconds: Optional[int]        = None


class MessageOut(BaseModel):
    chat_id:                int
    sender_id:              int
    receiver_id:            int
    message:                Optional[str]        = None
    message_type:           MESSAGE_TYPES        = "text"
    file_type:              Optional[FILE_TYPES] = None
    file_url:               Optional[str]        = None
    file_name:              Optional[str]        = None
    file_size_bytes:        Optional[int]        = None
    voice_duration_seconds: Optional[int]        = None
    status:                 str                  = "sent"
    sent_at:                datetime

    model_config = {"from_attributes": True}


# ── Conversation (for GET /chat/conversations) ────────────────────────────────

class ConversationUserOut(BaseModel):
    id:              int
    name:            str
    profile_picture: Optional[str] = None
    type_code:       str
    is_online:       bool = False


class ConversationOut(BaseModel):
    other_user:   ConversationUserOut
    last_message: MessageOut
    unread_count: int


# ── WebSocket payloads ────────────────────────────────────────────────────────

class WsMessageIn(BaseModel):
    type:        str = "message"   # message | typing | ping
    receiver_id: int | None = None
    message:     str | None = None
    is_typing:   bool | None = None


class WsMessageOut(BaseModel):
    type:        str
    chat_id:     int | None = None
    sender_id:   int | None = None
    receiver_id: int | None = None
    message:     str | None = None
    sent_at:     str | None = None
    is_typing:   bool | None = None
    online_users: list[int] | None = None
