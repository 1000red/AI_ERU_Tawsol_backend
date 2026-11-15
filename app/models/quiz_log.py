from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class QuizLog(Base):
    __tablename__ = "quiz_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(100), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    course_id = Column(String(20), nullable=True)
    file_id = Column(Integer, nullable=True)
    topic = Column(String(255), nullable=True)
    difficulty = Column(String(20), default="medium", nullable=False)  # easy, medium, hard
    num_questions = Column(Integer, default=5, nullable=False)
    questions_json = Column(Text, nullable=True)  # JSON representation of questions, choices, answers, explanations
    score = Column(Float, nullable=True)
    attempts_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User")
