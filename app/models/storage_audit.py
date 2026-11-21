from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from app.db.base import Base


class StorageAuditLog(Base):
    __tablename__ = "storage_audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    admin_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    admin_name = Column(String(100), nullable=True)
    action = Column(String(50), nullable=False)  # "quarantine", "restore", "replace", "permanent_delete", "sync"
    file_id = Column(Integer, nullable=True)
    file_title = Column(String(200), nullable=True)
    file_path = Column(String(500), nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True, default=0)
    bytes_freed = Column(BigInteger, nullable=True, default=0)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class StorageQuarantine(Base):
    __tablename__ = "storage_quarantines"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("material_files.file_id", ondelete="CASCADE"), nullable=False, unique=True)
    quarantined_by_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    original_path = Column(String(500), nullable=False)
    original_size = Column(BigInteger, nullable=True, default=0)
    quarantined_at = Column(DateTime, server_default=func.now(), nullable=False)
    purge_due_at = Column(DateTime, nullable=False)
    reason = Column(String(255), nullable=True)
