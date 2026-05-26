from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


# ── Assignment ────────────────────────────────────────────────────────────────

class Assignment(Base):
    __tablename__ = "assignments"

    assignment_id   = Column(Integer, primary_key=True, index=True, autoincrement=True)
    announcement_id = Column(Integer, ForeignKey("announcements.announcement_id"), nullable=True)
    material_id     = Column(String(10), ForeignKey("material.material_id"), nullable=False)
    author_id       = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    title           = Column(String(200), nullable=False)
    description     = Column(Text, nullable=True)
    file_type       = Column(String(20), nullable=True)
    file_path       = Column(String(500), nullable=True)
    link_url        = Column(String(500), nullable=True)
    text_content    = Column(Text, nullable=True)
    deadline        = Column(DateTime, nullable=False)
    created_at      = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at      = Column(DateTime, onupdate=func.now(), nullable=True)

    material     = relationship("Material",             back_populates="assignments")
    author       = relationship("User",                 back_populates="assignments")
    announcement = relationship("Announcement",         back_populates="assignment")
    submissions  = relationship("AssignmentSubmission", back_populates="assignment")


# ── AssignmentSubmission ──────────────────────────────────────────────────────

class AssignmentSubmission(Base):
    __tablename__ = "assignment_submissions"

    submission_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    assignment_id = Column(Integer, ForeignKey("assignments.assignment_id"), nullable=False)
    student_id    = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    title         = Column(String(200), nullable=True)
    description   = Column(Text, nullable=True)
    file_type     = Column(String(20), nullable=True)
    file_path     = Column(String(500), nullable=True)
    link_url      = Column(String(500), nullable=True)
    text_content  = Column(Text, nullable=True)
    submitted_at  = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at    = Column(DateTime, onupdate=func.now(), nullable=True)

    assignment = relationship("Assignment", back_populates="submissions")
    student    = relationship("User", back_populates="submissions")