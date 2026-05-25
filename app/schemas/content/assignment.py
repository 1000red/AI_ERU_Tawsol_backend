from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.schemas.file_types.__types__ import CONTENT_TYPE


# ── Assignment ────────────────────────────────────────────────────────────────

class AssignmentCreate(BaseModel):
    title:           str
    description:     Optional[str]                   = None
    deadline:        datetime
    file_type:       Optional[CONTENT_TYPE] = None
    link_url:        Optional[str]                   = None
    text_content:    Optional[str]                   = None
    material_id:     str
    announcement_id: Optional[int]                   = None


class AssignmentUpdate(BaseModel):
    title:        Optional[str]      = None
    description:  Optional[str]      = None
    deadline:     Optional[datetime] = None
    link_url:     Optional[str]      = None
    text_content: Optional[str]      = None


class AssignmentOut(BaseModel):
    title:           str
    description:     Optional[str]                   = None
    deadline:        datetime
    file_type:       Optional[CONTENT_TYPE] = None
    link_url:        Optional[str]                   = None
    text_content:    Optional[str]                   = None
    assignment_id:   int
    material_id:     str
    author_id:       int
    announcement_id: Optional[int]                   = None
    file_path:       Optional[str]                   = None
    created_at:      datetime
    updated_at:      Optional[datetime]              = None

    model_config = {"from_attributes": True}


# ── AssignmentSubmission ──────────────────────────────────────────────────────

class SubmissionCreate(BaseModel):
    title:         Optional[str]                    = None
    description:   Optional[str]                    = None
    file_type:     Optional[CONTENT_TYPE]  = None
    link_url:      Optional[str]                    = None
    text_content:  Optional[str]                    = None
    assignment_id: int


class SubmissionUpdate(BaseModel):
    title:        Optional[str] = None
    description:  Optional[str] = None
    link_url:     Optional[str] = None
    text_content: Optional[str] = None


class SubmissionOut(BaseModel):
    title:         Optional[str]                    = None
    description:   Optional[str]                    = None
    file_type:     Optional[CONTENT_TYPE]  = None
    link_url:      Optional[str]                    = None
    text_content:  Optional[str]                    = None
    submission_id: int
    assignment_id: int
    student_id:    int
    file_path:     Optional[str]                    = None
    submitted_at:  datetime
    updated_at:    Optional[datetime]               = None

    model_config = {"from_attributes": True}
