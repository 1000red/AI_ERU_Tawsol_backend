from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.schemas.file_types.__types__ import CONTENT_TYPE


# ── MaterialFile ──────────────────────────────────────────────────────────────

class MaterialFileCreate(BaseModel):
    title:           str
    description:     Optional[str]          = None
    file_type:       CONTENT_TYPE
    link_url:        Optional[str]          = None
    text_content:    Optional[str]          = None
    material_id:     Optional[str]          = None
    announcement_id: Optional[int]          = None


class MaterialFileUpdate(BaseModel):
    title:        Optional[str] = None
    description:  Optional[str] = None
    link_url:     Optional[str] = None
    text_content: Optional[str] = None


class MaterialFileOut(BaseModel):
    title:           str
    description:     Optional[str]          = None
    file_type:       CONTENT_TYPE
    link_url:        Optional[str]          = None
    text_content:    Optional[str]          = None
    file_id:         int
    material_id:     Optional[str]          = None
    author_id:       int
    announcement_id: Optional[int]          = None
    file_path:       Optional[str]          = None
    file_size:       Optional[int]          = None  # bytes
    author_type_code: Optional[str]         = None  # DR | TA | ADM
    created_at:      datetime
    updated_at:      Optional[datetime]     = None

    model_config = {"from_attributes": True}
