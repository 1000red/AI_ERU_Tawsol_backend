from pydantic import BaseModel
from typing import Optional, Literal, List
from datetime import datetime

TARGET_TYPE = Literal[
    "all", "course", "course_department", "department", "level",
    "student",  # single student (legacy)
    "users",    # explicit multi-user list via target_user_ids
]


# ── Announcement ──────────────────────────────────────────────────────────────

class AnnouncementCreate(BaseModel):
    title:             str
    content:           str
    announcement_type: Literal["normal", "material_file", "assignment"] = "normal"
    priority:          Literal["normal", "important", "urgent"]         = "normal"
    target_type:       TARGET_TYPE
    target_course_id:  Optional[str]       = None
    target_department: Optional[str]       = None
    target_year:       Optional[int]       = None
    target_student_id: Optional[int]       = None   # single-student shorthand
    target_user_ids:   Optional[List[int]] = None   # explicit list (target_type="users")


class AnnouncementUpdate(BaseModel):
    title:   Optional[str] = None
    content: Optional[str] = None


class AnnouncementOut(BaseModel):
    announcement_id:   int
    author_id:         int
    title:             str
    content:           str
    announcement_type: str
    priority:          str
    target_type:       str
    target_course_id:  Optional[str]  = None
    target_department: Optional[str]  = None
    target_year:       Optional[int]  = None
    target_student_id: Optional[int]  = None
    target_user_ids:   List[int]      = []
    created_at:        datetime
    updated_at:        Optional[datetime] = None
    is_read:           bool           = False
    author_name:       Optional[str]  = None
    subject_name:      Optional[str]  = None
    subject_code:      Optional[str]  = None

    model_config = {"from_attributes": True}


# ── Recipient listing ─────────────────────────────────────────────────────────

class RecipientOut(BaseModel):
    user_id:         int
    name:            str
    uni_code:        str
    type_code:       str
    department:      Optional[str] = None
    level:           Optional[int] = None
    profile_picture: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Unread count ──────────────────────────────────────────────────────────────

class UnreadCountOut(BaseModel):
    unread_count: int
