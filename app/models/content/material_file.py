from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class MaterialFile(Base):
    __tablename__ = "material_files"

    file_id         = Column(Integer, primary_key=True, index=True, autoincrement=True)
    announcement_id = Column(Integer, ForeignKey("announcements.announcement_id"), nullable=True)
    material_id     = Column(String(10), ForeignKey("material.material_id"), nullable=True)
    author_id       = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    title           = Column(String(200), nullable=False)
    description     = Column(Text, nullable=True)
    file_type       = Column(String(20), nullable=False)  # pdf, word, ppt, python, jupyter, image, video, voice, text
    file_path       = Column(String(500), nullable=True)
    file_size       = Column(BigInteger, nullable=True)  # bytes
    link_url        = Column(String(500), nullable=True)
    text_content    = Column(Text, nullable=True)
    created_at      = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at      = Column(DateTime, onupdate=func.now(), nullable=True)

    material     = relationship("Material", back_populates="files")
    author       = relationship("User", back_populates="material_files")
    announcement = relationship("Announcement", back_populates="material_file")

    @property
    def author_type_code(self) -> str | None:
        return self.author.type_code if self.author else None