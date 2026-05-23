from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.schemas.file_types.__types__ import FILE_TYPES


# ── MaterialFile ──────────────────────────────────────────────────────────────

class MaterialFileCreate(BaseModel):
    title:           str
    description:     Optional[str]          = None
    file_type:       FILE_TYPES
    link_url:        Optional[str]          = None
    text_content:    Optional[str]          = None
    material_id:     str
    announcement_id: Optional[int]          = None


class MaterialFileUpdate(BaseModel):
    title:        Optional[str] = None
    description:  Optional[str] = None
    link_url:     Optional[str] = None
    text_content: Optional[str] = None


class MaterialFileOut(BaseModel):
    title:           str
    description:     Optional[str]          = None
    file_type:       FILE_TYPES
    link_url:        Optional[str]          = None
    text_content:    Optional[str]          = None
    file_id:         int
    material_id:     str
    author_id:       int
    announcement_id: Optional[int]          = None
    file_path:       Optional[str]          = None
    created_at:      datetime
    updated_at:      Optional[datetime]     = None

    model_config = {"from_attributes": True}
