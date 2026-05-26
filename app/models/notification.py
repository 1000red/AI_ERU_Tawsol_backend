from app.db.base import Base
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id         = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id    = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    token      = Column(String(512), nullable=False, unique=True)
    platform   = Column(String(10), default="android")
    active     = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="device_tokens")


class AppNotification(Base):
    __tablename__ = "app_notifications"

    id         = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    title      = Column(String(200), nullable=False)
    body       = Column(Text, nullable=True)
    # "announcement" | "assignment" | "material" | "system"
    notif_type = Column(String(30), nullable=False, default="announcement")
    ref_id     = Column(Integer, nullable=True)   # announcement_id / assignment_id
    is_read    = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User")
