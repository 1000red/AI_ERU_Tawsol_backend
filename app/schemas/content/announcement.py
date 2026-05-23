from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


# ── Announcement ──────────────────────────────────────────────────────────────

class AnnouncementCreate(BaseModel):
    title:             str
    content:           str
    announcement_type: Literal["normal", "material_file", "assignment"] = "normal"
    priority:          Literal["normal", "important", "urgent"] = "normal"
    target_type:       Literal["all", "course", "course_department", "department", "level", "student"]
    target_course_id:  Optional[str] = None
    target_department: Optional[str] = None
    target_year:       Optional[int] = None
    target_student_id: Optional[int] = None


class AnnouncementUpdate(BaseModel):
    title:   Optional[str] = None
    content: Optional[str] = None


class AnnouncementOut(BaseModel):
    title:             str
    content:           str
    announcement_type: Literal["normal", "material_file", "assignment"] = "normal"
    priority:          Literal["normal", "important", "urgent"] = "normal"
    target_type:       Literal["all", "course", "course_department", "department", "level", "student"]
    target_course_id:  Optional[str]  = None
    target_department: Optional[str]  = None
    target_year:       Optional[int]  = None
    target_student_id: Optional[int]  = None
    announcement_id:   int
    author_id:         int
    created_at:        datetime
    updated_at:        Optional[datetime] = None
    is_read:           bool          = False
    author_name:       Optional[str] = None
    subject_name:      Optional[str] = None
    subject_code:      Optional[str] = None

    model_config = {"from_attributes": True}
