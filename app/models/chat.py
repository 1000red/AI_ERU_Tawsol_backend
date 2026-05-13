from app.db.base import Base
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

class ChatHistory(Base):
    __tablename__ = "chat_history"

    chat_id     = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sender_id   = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    message     = Column(Text, nullable=False)
    sent_at     = Column(DateTime, server_default=func.now(), nullable=False)

    sender   = relationship("User", foreign_keys=[sender_id],   back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")
