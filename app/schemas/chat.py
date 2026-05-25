from pydantic import BaseModel, computed_field
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
    file_size_mb:           Optional[float]      = None
    voice_duration_seconds: Optional[int]        = None
    status:                 str                  = "sent"
    sent_at:                datetime

    model_config = {"from_attributes": True}

    def model_post_init(self, __context) -> None:
        if self.file_size_bytes is not None and self.file_size_mb is None:
            object.__setattr__(self, "file_size_mb", round(self.file_size_bytes / (1024 * 1024), 3))


# ── Conversation (for GET /chat/conversations) ────────────────────────────────

class ConversationUserOut(BaseModel):
    id:              int
    name:            str
    profile_picture: Optional[str]      = None
    type_code:       str
    is_online:       bool               = False
    last_seen:       Optional[datetime] = None
    student_id:      Optional[str]      = None   # uni_code


class ConversationOut(BaseModel):
    id:           str                      # "{min_id}_{max_id}"
    other_user:   ConversationUserOut
    last_message: Optional[MessageOut]     = None
    unread_count: int
    is_pinned:    bool                     = False


# ── WebSocket payloads ────────────────────────────────────────────────────────

class WsMessageIn(BaseModel):
    type:        str = "message"   # message | typing | ping | seen
    receiver_id: int | None = None
    sender_id:   int | None = None   # used in "seen" events
    message:     str | None = None
    is_typing:   bool | None = None


class WsMessageOut(BaseModel):
    type:         str
    chat_id:      int | None = None
    sender_id:    int | None = None
    receiver_id:  int | None = None
    message:      str | None = None
    sent_at:      str | None = None
    status:       str | None = None
    is_typing:    bool | None = None
    online_users: list[int] | None = None
