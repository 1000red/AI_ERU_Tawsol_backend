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

    announcement_type = Column(String(20), nullable=False, default="normal")  # "normal", "material_file", "assignment"
    priority          = Column(String(10), nullable=False, default="normal")  # "normal", "important", "urgent"

    # Target — "all" | "course" | "course_department" | "department" | "level" | "student" | "users" | "role"
    target_type       = Column(String(20), nullable=False)
    target_course_id  = Column(String(10), ForeignKey("material.material_id"), nullable=True) # if DR larning two course
    target_department = Column(String(100), nullable=True) # Ai /CS /DS /Soft
    target_year       = Column(Integer, nullable=True) # level
    target_student_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)  # single-student shorthand
    target_role       = Column(String(10), nullable=True)  # STU | DR | TA — used with target_type="role"

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now(), nullable=True)

    author         = relationship("User", foreign_keys=[author_id],          back_populates="announcements")
    target_course  = relationship("Material", foreign_keys=[target_course_id], back_populates="announcements")
    target_student = relationship("User", foreign_keys=[target_student_id])
    material_file  = relationship("MaterialFile", back_populates="announcement", uselist=False)
    assignment     = relationship("Assignment",   back_populates="announcement", uselist=False)
    reads          = relationship("AnnouncementRead",       back_populates="announcement", cascade="all, delete-orphan")
    target_users   = relationship("AnnouncementTargetUser", back_populates="announcement", cascade="all, delete-orphan")


# ── AnnouncementTargetUser — explicit multi-user recipient list ───────────────

class AnnouncementTargetUser(Base):
    """Used when target_type == 'users': maps an announcement to each recipient."""
    __tablename__ = "announcement_target_users"
    __table_args__ = (
        UniqueConstraint("announcement_id", "user_id", name="uq_ann_target_user"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    announcement_id = Column(Integer, ForeignKey("announcements.announcement_id", ondelete="CASCADE"), nullable=False)
    user_id         = Column(Integer, ForeignKey("users.user_id",         ondelete="CASCADE"), nullable=False)

    announcement = relationship("Announcement", back_populates="target_users")
    user         = relationship("User")


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