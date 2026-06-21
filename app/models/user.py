from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.db.base import Base


class UserType(Base):
    __tablename__ = "user_type"

    code        = Column(String(5), primary_key=True) # "STU", "DR", "TA", "ADM"
    description = Column(String(50), nullable=False)

    users = relationship("User", back_populates="user_type")


class User(Base):
    __tablename__ = "users"

    user_id  = Column(Integer, primary_key=True, index=True, autoincrement=True)
    uni_code = Column(String(20), nullable=False, unique=True)
    name     = Column(String(100), nullable=False)
    email    = Column(String(100), nullable=False, unique=True, index=True)
    password = Column(String(255), nullable=False)
    level    = Column(Integer, nullable=False, default=0) # from 1 to 4 for students, 100 for admins
    department = Column(String(100), nullable=True) # AI /CS /DS /SW /general(level 1 and 2 and 100 for else)
    type_code            = Column(String(5), ForeignKey("user_type.code"), nullable=False)
    current_password = Column(Boolean, nullable=False, default=True)
    last_seen         = Column(DateTime(timezone=True), nullable=True)

    user_type         = relationship("UserType", back_populates="users")
    sent_messages     = relationship("ChatHistory", foreign_keys="ChatHistory.sender_id",   back_populates="sender")
    received_messages = relationship("ChatHistory", foreign_keys="ChatHistory.receiver_id", back_populates="receiver")
    announcements     = relationship("Announcement",          foreign_keys="Announcement.author_id",          back_populates="author")
    material_files    = relationship("MaterialFile",          foreign_keys="MaterialFile.author_id",          back_populates="author")
    assignments       = relationship("Assignment",            foreign_keys="Assignment.author_id",            back_populates="author")

