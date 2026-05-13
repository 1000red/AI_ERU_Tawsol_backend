from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


# ── Announcement ──────────────────────────────────────────────────────────────

class AnnouncementBase(BaseModel):
    title:             str
    content:           str
    announcement_type: Literal["normal", "material_file", "assignment"] = "normal"
    target_type:       Literal["all", "course", "course_department", "department", "level", "student"]
    target_course_id:  Optional[int]  = None
    target_department: Optional[str]  = None
    target_year:       Optional[int]  = None
    target_student_id: Optional[int]  = None


class AnnouncementCreate(AnnouncementBase):
    pass


class AnnouncementUpdate(BaseModel):
    title:   Optional[str] = None
    content: Optional[str] = None


class AnnouncementOut(AnnouncementBase):
    announcement_id: int
    author_id:       int
    created_at:      datetime
    updated_at:      Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── MaterialFile ──────────────────────────────────────────────────────────────

class MaterialFileBase(BaseModel):
    title:        str
    description:  Optional[str] = None
    file_type:    Literal["pdf", "word", "ppt", "python", "jupyter", "image", "video", "voice", "link", "text"]
    link_url:     Optional[str] = None
    text_content: Optional[str] = None


class MaterialFileCreate(MaterialFileBase):
    material_id:     int
    announcement_id: Optional[int] = None


class MaterialFileUpdate(BaseModel):
    title:        Optional[str] = None
    description:  Optional[str] = None
    link_url:     Optional[str] = None
    text_content: Optional[str] = None


class MaterialFileOut(MaterialFileBase):
    file_id:         int
    material_id:     int
    author_id:       int
    announcement_id: Optional[int] = None
    file_path:       Optional[str] = None
    created_at:      datetime
    updated_at:      Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Assignment ────────────────────────────────────────────────────────────────

class AssignmentBase(BaseModel):
    title:        str
    description:  Optional[str] = None
    deadline:     datetime
    file_type:    Optional[Literal["pdf", "word", "ppt", "python", "jupyter", "image", "video", "voice", "link", "text"]] = None
    link_url:     Optional[str] = None
    text_content: Optional[str] = None


class AssignmentCreate(AssignmentBase):
    material_id:     int
    announcement_id: Optional[int] = None


class AssignmentUpdate(BaseModel):
    title:        Optional[str]      = None
    description:  Optional[str]      = None
    deadline:     Optional[datetime] = None
    link_url:     Optional[str]      = None
    text_content: Optional[str]      = None


class AssignmentOut(AssignmentBase):
    assignment_id:   int
    material_id:     int
    author_id:       int
    announcement_id: Optional[int] = None
    file_path:       Optional[str] = None
    created_at:      datetime
    updated_at:      Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── AssignmentSubmission ──────────────────────────────────────────────────────

class SubmissionBase(BaseModel):
    title:        Optional[str] = None
    description:  Optional[str] = None
    file_type:    Optional[Literal["pdf", "word", "image", "voice", "link", "text"]] = None
    link_url:     Optional[str] = None
    text_content: Optional[str] = None


class SubmissionCreate(SubmissionBase):
    assignment_id: int


class SubmissionUpdate(BaseModel):
    title:        Optional[str] = None
    description:  Optional[str] = None
    link_url:     Optional[str] = None
    text_content: Optional[str] = None


class SubmissionOut(SubmissionBase):
    submission_id: int
    assignment_id: int
    student_id:    int
    file_path:     Optional[str] = None
    submitted_at:  datetime
    updated_at:    Optional[datetime] = None

    model_config = {"from_attributes": True}