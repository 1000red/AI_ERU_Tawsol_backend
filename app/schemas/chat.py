from pydantic import BaseModel
from datetime import datetime


class MessageSend(BaseModel):
    sender_id:   int
    receiver_id: int
    message:     str


class MessageOut(BaseModel):
    chat_id:     int
    sender_id:   int
    receiver_id: int
    message:     str
    sent_at:     datetime

    model_config = {"from_attributes": True}


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
