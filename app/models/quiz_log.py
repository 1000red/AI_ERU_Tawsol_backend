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


class QuizStudentAttempt(Base):
    __tablename__ = "quiz_student_attempts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(100), index=True, nullable=False)
    quiz_log_id = Column(Integer, ForeignKey("quiz_logs.id", ondelete="CASCADE"), nullable=True)
    student_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Float, nullable=False)
    total_questions = Column(Integer, default=5, nullable=False)
    correct_count = Column(Integer, default=0, nullable=False)
    answers_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    student = relationship("User")
    quiz_log = relationship("QuizLog", backref="student_attempts")

