from app.db.base import Base
from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

class ChatHistory(Base):
    __tablename__ = "chat_history"

    chat_id                = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sender_id              = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    receiver_id            = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    message                = Column(Text, nullable=True)
    content_type           = Column(String(20), nullable=False, default="text")
    file_url               = Column(String(500), nullable=True)
    file_name              = Column(String(255), nullable=True)
    file_size_bytes        = Column(Integer, nullable=True)
    voice_duration_seconds = Column(Integer, nullable=True)
    status                 = Column(String(10), nullable=False, default="sent")  # sent | delivered | seen
    is_deleted             = Column(Boolean, nullable=False, default=False)
    edited_at              = Column(DateTime, nullable=True)
    sent_at                = Column(DateTime, server_default=func.now(), nullable=False)
    reply_to_id            = Column(Integer, ForeignKey("chat_history.chat_id"), nullable=True)

    sender   = relationship("User", foreign_keys=[sender_id],   back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")
    # Self-Referencing Relationship
    reply_to = relationship("ChatHistory", foreign_keys="ChatHistory.reply_to_id", remote_side="ChatHistory.chat_id")


class PinnedConversation(Base):
    __tablename__ = "pinned_conversations"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    partner_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    pinned_at  = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "partner_id", name="uq_pinned_user_partner"),)
