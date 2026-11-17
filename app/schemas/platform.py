from typing import Optional
from pydantic import BaseModel, Field


class PlatformStatusUpdate(BaseModel):
    is_active: bool
    maintenance_message: Optional[str] = Field(default=None, max_length=1000)


class PublicPlatformStatusOut(BaseModel):
    is_active: bool
    maintenance_mode: bool
    maintenance_message: str
    stopped_at: Optional[str] = None
    updated_at: Optional[str] = None


class PlatformStatusOut(PublicPlatformStatusOut):
    updated_by: Optional[int] = None
    updated_by_name: Optional[str] = None
