from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.schemas.file_types.__types__ import CONTENT_TYPE
from app.schemas.content.material_file import MaterialFileOut


# ── Assignment ────────────────────────────────────────────────────────────────

class AssignmentCreate(BaseModel):
    title:           str
    description:     Optional[str]           = None
    deadline:        datetime
    file_type:       Optional[CONTENT_TYPE]  = None
    link_url:        Optional[str]           = None
    text_content:    Optional[str]           = None
    material_id:     str
    announcement_id: Optional[int]           = None


class AssignmentUpdate(BaseModel):
    title:        Optional[str]      = None
    description:  Optional[str]      = None
    deadline:     Optional[datetime] = None
    link_url:     Optional[str]      = None
    text_content: Optional[str]      = None


class AssignmentOut(BaseModel):
    assignment_id:   int
    material_id:     str
    author_id:       int
    announcement_id: Optional[int]          = None
    title:           str
    description:     Optional[str]          = None
    deadline:        datetime
    file_type:       Optional[CONTENT_TYPE] = None
    file_path:       Optional[str]          = None
    link_url:        Optional[str]          = None
    text_content:    Optional[str]          = None
    created_at:      datetime
    updated_at:      Optional[datetime]     = None
    # Enriched fields (populated by service, None when not applicable)
    has_submitted:      Optional[bool] = None   # for students
    my_submission_id:   Optional[int]  = None   # for students
    submission_count:   Optional[int]  = None   # for DR/TA/ADM
    author_name:        Optional[str]  = None
    subject_name:       Optional[str]  = None
    subject_code:       Optional[str]  = None
    attachments:        List[MaterialFileOut] = []

    model_config = {"from_attributes": True}


# ── Submission ────────────────────────────────────────────────────────────────

class SubmissionCreate(BaseModel):
    title:         Optional[str]           = None
    description:   Optional[str]           = None
    file_type:     Optional[CONTENT_TYPE]  = None
    link_url:      Optional[str]           = None
    text_content:  Optional[str]           = None
    assignment_id: int


class SubmissionUpdate(BaseModel):
    title:        Optional[str] = None
    description:  Optional[str] = None
    link_url:     Optional[str] = None
    text_content: Optional[str] = None


class SubmissionOut(BaseModel):
    submission_id: int
    assignment_id: int
    student_id:    int
    title:         Optional[str]           = None
    description:   Optional[str]           = None
    file_type:     Optional[CONTENT_TYPE]  = None
    file_path:     Optional[str]           = None
    link_url:      Optional[str]           = None
    text_content:  Optional[str]           = None
    submitted_at:  datetime
    updated_at:    Optional[datetime]      = None
    student_name:  Optional[str]           = None   # enriched

    model_config = {"from_attributes": True}
