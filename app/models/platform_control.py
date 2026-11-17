from sqlalchemy import Column, Integer, Boolean, Text, String, DateTime
from sqlalchemy.sql import func
from app.db.base import Base

DEFAULT_MAINTENANCE_MESSAGE = (
    "المنصة متوقفة مؤقتاً من قبل إدارة مدرسة WE للتكنولوجيا التطبيقية بالسويس "
    "لأغراض الصيانة والتحديث. نعتذر عن الإزعاج وسنعود للعمل قريباً."
)


class PlatformControl(Base):
    """Singleton table storing the global platform on/off switch and maintenance message."""

    __tablename__ = "platform_control"

    id = Column(Integer, primary_key=True, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    maintenance_message = Column(
        Text,
        nullable=False,
        default=DEFAULT_MAINTENANCE_MESSAGE,
    )
    stopped_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )
    updated_by = Column(Integer, nullable=True)
    updated_by_name = Column(String(150), nullable=True)
