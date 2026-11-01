from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.schemas.file_types.__types__ import CONTENT_TYPE


class MessageEdit(BaseModel):
    message: str


class RepliedMessageOut(BaseModel):
    chat_id:      int
    sender_id:    int
    content_type: str
    message:      Optional[str] = None
    file_name:    Optional[str] = None
    is_deleted:   bool          = False

    model_config = {"from_attributes": True}


class MessageSend(BaseModel):
    receiver_id:            int
    content_type:           CONTENT_TYPE         = "text"
    message:                Optional[str]        = None
    file_url:               Optional[str]        = None
    file_name:              Optional[str]        = None
    file_size_bytes:        Optional[int]        = None
    voice_duration_seconds: Optional[int]        = None
    reply_to_id:            Optional[int]        = None


class MessageOut(BaseModel):
    chat_id:                int
    sender_id:              int
    receiver_id:            int
    content_type:           CONTENT_TYPE         = "text"
    message:                Optional[str]        = None
    file_url:               Optional[str]        = None
    file_name:              Optional[str]        = None
    file_size_bytes:        Optional[int]        = None
    file_size_mb:           Optional[float]      = None
    voice_duration_seconds: Optional[int]        = None
    status:                 str                  = "sent"
    is_deleted:             bool                 = False
    edited_at:              Optional[datetime]   = None
    sent_at:                datetime
    reply_to_id:            Optional[int]               = None
    reply_to:               Optional[RepliedMessageOut] = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context) -> None:
        if self.file_size_bytes is not None and self.file_size_mb is None:
            object.__setattr__(self, "file_size_mb", round(self.file_size_bytes / (1024 * 1024), 3))


# ── Conversation ──────────────────────────────────────────────────────────────

class ConversationUserOut(BaseModel):
    id:              int
    name:            str
    type_code:       str
    is_online:       bool               = False
    last_seen:       Optional[datetime] = None
    student_id:      Optional[str]      = None


class ConversationOut(BaseModel):
    id:           str
    other_user:   ConversationUserOut
    last_message: Optional[MessageOut]  = None
    unread_count: int
    is_pinned:    bool                  = False


# ── WebSocket payloads ────────────────────────────────────────────────────────

class WsMessageIn(BaseModel):
    type:         str          = "message"   # message | typing | ping | seen
    receiver_id:  int | None   = None
    sender_id:    int | None   = None
    content_type: str | None   = "text"
    message:      str | None   = None
    is_typing:    bool | None  = None


class WsMessageOut(BaseModel):
    type:         str
    chat_id:      int | None   = None
    sender_id:    int | None   = None
    receiver_id:  int | None   = None
    content_type: str | None   = None
    message:      str | None   = None
    sent_at:      str | None   = None
    status:       str | None   = None
    is_typing:    bool | None  = None
    online_users: list[int] | None = None
