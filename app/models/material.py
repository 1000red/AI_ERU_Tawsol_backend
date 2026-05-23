from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class Material(Base):
    __tablename__ = "material"

    material_id = Column(String(10), primary_key=True, index=True)
    name        = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    duration    = Column(Integer, nullable=False, default=0) # in hours
    profile_picture = Column(String(255), nullable=True) # path to image file


    student_enrollments = relationship("MaterialStudent", back_populates="material")
    teacher_assignments = relationship("MaterialTeacher", back_populates="material")
    complaints          = relationship("Complaint",       back_populates="material")
    announcements       = relationship("Announcement",   back_populates="target_course", foreign_keys="Announcement.target_course_id")
    files               = relationship("MaterialFile",   back_populates="material")
    assignments         = relationship("Assignment",     back_populates="material")


class MaterialStudent(Base):
    __tablename__ = "material_student"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(String(10), ForeignKey("material.material_id"), nullable=False)
    user_id     = Column(Integer, ForeignKey("users.user_id"),        nullable=False)

    material = relationship("Material", back_populates="student_enrollments")
    student  = relationship("User")


class MaterialTeacher(Base):
    __tablename__ = "material_teacher"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(String(10), ForeignKey("material.material_id"), nullable=False)
    user_id     = Column(Integer, ForeignKey("users.user_id"),        nullable=False)

    material = relationship("Material", back_populates="teacher_assignments")
    teacher  = relationship("User")
