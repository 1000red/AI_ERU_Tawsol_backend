from app.db.base import Base
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

class Complaint(Base):
    __tablename__ = "complaints"

    complaint_id   = Column(Integer, primary_key=True, index=True, autoincrement=True)
    material_id    = Column(Integer, ForeignKey("material.material_id"), nullable=False)
    student_id     = Column(Integer, ForeignKey("users.user_id"),        nullable=False)
    teacher_id     = Column(Integer, ForeignKey("users.user_id"),        nullable=False)
    complaint_text = Column(Text, nullable=False)
    send_at        = Column(DateTime, server_default=func.now(), nullable=False)

    material = relationship("Material", back_populates="complaints")
    student  = relationship("User", foreign_keys=[student_id])
    teacher  = relationship("User", foreign_keys=[teacher_id])
