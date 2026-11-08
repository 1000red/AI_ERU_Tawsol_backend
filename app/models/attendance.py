from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class AttendanceSession(Base):
    __tablename__ = "attendance_session"

    session_id  = Column(Integer, primary_key=True, autoincrement=True, index=True)
    material_id = Column(String(10), ForeignKey("material.material_id"), nullable=False, index=True)
    created_by  = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    title       = Column(String(100), nullable=False, default="محاضرة")
    token       = Column(String(64), nullable=False, unique=True, index=True)
    expires_at  = Column(DateTime(timezone=True), nullable=False)
    is_active   = Column(Boolean, nullable=False, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    records     = relationship("AttendanceRecord", back_populates="session", cascade="all, delete-orphan")
    material    = relationship("Material")
    creator     = relationship("User", foreign_keys=[created_by])


class AttendanceRecord(Base):
    __tablename__ = "attendance_record"

    record_id   = Column(Integer, primary_key=True, autoincrement=True, index=True)
    session_id  = Column(Integer, ForeignKey("attendance_session.session_id", ondelete="CASCADE"), nullable=False, index=True)
    material_id = Column(String(10), ForeignKey("material.material_id"), nullable=False)
    student_id  = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    scanned_at  = Column(DateTime(timezone=True), server_default=func.now())
    status      = Column(String(20), nullable=False, default="PRESENT") # PRESENT, LATE, EXCUSED

    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_session_student_attendance"),
    )

    session     = relationship("AttendanceSession", back_populates="records")
    student     = relationship("User", foreign_keys=[student_id])
    material    = relationship("Material")
