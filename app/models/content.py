from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
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

    # نوع الإعلان
    announcement_type = Column(String(20), nullable=False, default="normal")  # "normal", "material_file", "assignment"

    # Target
    target_type       = Column(String(20), nullable=False)  # "all", "course", "course_department", "department", "level", "student"
    target_course_id  = Column(Integer, ForeignKey("material.material_id"), nullable=True)
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


# ── MaterialFile ──────────────────────────────────────────────────────────────

class MaterialFile(Base):
    __tablename__ = "material_files"

    file_id         = Column(Integer, primary_key=True, index=True, autoincrement=True)
    announcement_id = Column(Integer, ForeignKey("announcements.announcement_id"), nullable=True)
    material_id     = Column(Integer, ForeignKey("material.material_id"), nullable=False)
    author_id       = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    title           = Column(String(200), nullable=False)
    description     = Column(Text, nullable=True)
    file_type       = Column(String(20), nullable=False)  # pdf, word, ppt, python, jupyter, image, video, voice, link, text
    file_path       = Column(String(500), nullable=True)
    link_url        = Column(String(500), nullable=True)
    text_content    = Column(Text, nullable=True)
    created_at      = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at      = Column(DateTime, onupdate=func.now(), nullable=True)

    material     = relationship("Material", back_populates="files")
    author       = relationship("User", back_populates="material_files")
    announcement = relationship("Announcement", back_populates="material_file")


# ── Assignment ────────────────────────────────────────────────────────────────

class Assignment(Base):
    __tablename__ = "assignments"

    assignment_id   = Column(Integer, primary_key=True, index=True, autoincrement=True)
    announcement_id = Column(Integer, ForeignKey("announcements.announcement_id"), nullable=True)
    material_id     = Column(Integer, ForeignKey("material.material_id"), nullable=False)
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
    file_type     = Column(String(20), nullable=True)  # pdf, word, image, voice, link, text
    file_path     = Column(String(500), nullable=True)
    link_url      = Column(String(500), nullable=True)
    text_content  = Column(Text, nullable=True)
    submitted_at  = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at    = Column(DateTime, onupdate=func.now(), nullable=True)

    assignment = relationship("Assignment", back_populates="submissions")
    student    = relationship("User", back_populates="submissions")