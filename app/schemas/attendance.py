from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AttendanceSessionCreate(BaseModel):
    material_id: str
    title: Optional[str] = "محاضرة"
    duration_minutes: Optional[int] = 15


class AttendanceAttendee(BaseModel):
    record_id: int
    student_id: int
    student_name: str
    student_unicode: str
    scanned_at: datetime
    status: str

    model_config = {"from_attributes": True}


class AttendanceSessionOut(BaseModel):
    session_id: int
    material_id: str
    course_name: Optional[str] = None
    title: str
    token: str
    qr_payload: str
    expires_at: datetime
    is_active: bool
    created_at: datetime
    total_attended: int = 0
    attendees: Optional[list[AttendanceAttendee]] = None

    model_config = {"from_attributes": True}


class AttendanceCheckInRequest(BaseModel):
    token: str


class AttendanceCheckInOut(BaseModel):
    message: str
    record_id: int
    session_id: int
    material_id: str
    course_name: str
    scanned_at: datetime
    status: str


class StudentCourseAttendanceSummary(BaseModel):
    material_id: str
    course_name: str
    attended_sessions: int
    total_sessions: int
    attendance_rate: float # e.g. 90.0%
