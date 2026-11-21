"""Administrative Security Audit Log Model.

Captures all security-critical operations, authentication events, account lockouts,
platform kill-switch status toggles, user mutations, and administrative overrides.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.db.base import Base


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    admin_id = Column(Integer, nullable=True, index=True)
    admin_email = Column(String(100), nullable=True, index=True)
    admin_name = Column(String(100), nullable=True)
    action = Column(String(50), nullable=False, index=True)
    target_resource = Column(String(100), nullable=True, index=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
