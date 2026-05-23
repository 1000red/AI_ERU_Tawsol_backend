from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


# ── Announcement ──────────────────────────────────────────────────────────────

class Announcement(Base):
    __tablename__ = "announcements"

    announcement_id   = Column(Integer, primary_key=True, index=True, autoincrement=True)
    author_id         = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    title             = Column(String(200), nullable=False)
    content           = Column(Text, nullable=False)

    # announcement_type
    announcement_type = Column(String(20), nullable=False, default="normal")  # "normal", "material_file", "assignment"
    priority          = Column(String(10), nullable=False, default="normal")  # "normal", "important", "urgent"

    # Target
    target_type       = Column(String(20), nullable=False)  # "all", "course", "course_department", "department", "level", "student"
    target_course_id  = Column(String(10), ForeignKey("material.material_id"), nullable=True)
    target_department = Column(String(100), nullable=True)
    target_year       = Column(Integer, nullable=True)
    target_student_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now(), nullable=True)

    author         = relationship("User", foreign_keys=[author_id],         back_populates="announcements")
    target_course  = relationship("Material", foreign_keys=[target_course_id], back_populates="announcements")
    target_student = relationship("User", foreign_keys=[target_student_id])
    material_file  = relationship("MaterialFile", back_populates="announcement", uselist=False)
    assignment     = relationship("Assignment",   back_populates="announcement", uselist=False)
    reads          = relationship("AnnouncementRead", back_populates="announcement", cascade="all, delete-orphan")


# ── AnnouncementRead ──────────────────────────────────────────────────────────

class AnnouncementRead(Base):
    __tablename__ = "announcement_reads"
    __table_args__ = (
        UniqueConstraint("user_id", "announcement_id", name="uq_announcement_reads_user_ann"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    user_id         = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    announcement_id = Column(Integer, ForeignKey("announcements.announcement_id"), nullable=False)
    read_at         = Column(DateTime, server_default=func.now(), nullable=False)

    announcement = relationship("Announcement", back_populates="reads")