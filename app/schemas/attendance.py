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


class AttendancePublicCheckInRequest(BaseModel):
    token: str
    student_identifier: str  # student_id, uni_code, or email
    pin: Optional[str] = None


class AttendanceCheckInOut(BaseModel):
    message: str
    record_id: Optional[int] = None
    session_id: int
    material_id: str
    course_name: str
    scanned_at: Optional[datetime] = None
    status: str
    success: bool = True
    student_name: Optional[str] = None
    student_uni_code: Optional[str] = None


class StudentCourseAttendanceSummary(BaseModel):
    material_id: str
    course_name: str
    attended_sessions: int
    total_sessions: int
    attendance_rate: float # e.g. 90.0%


# ── Full Attendance Sheet & Teacher Marking Schemas ──────────────────────────
class AttendanceMarkRequest(BaseModel):
    student_id: int
    status: str = "PRESENT"  # PRESENT, LATE, EXCUSED, ABSENT


class AttendanceBatchMarkRequest(BaseModel):
    records: list[AttendanceMarkRequest]


class AttendanceSheetStudent(BaseModel):
    student_id: int
    name: str
    uni_code: Optional[str] = None
    email: Optional[str] = None
    status: str = "ABSENT"  # PRESENT, LATE, EXCUSED, ABSENT
    scanned_at: Optional[datetime] = None
    record_id: Optional[int] = None


class AttendanceSheetSummary(BaseModel):
    total_enrolled: int = 0
    present_count: int = 0
    late_count: int = 0
    excused_count: int = 0
    absent_count: int = 0
    attendance_rate: float = 0.0


class AttendanceSheetOut(BaseModel):
    session_id: int
    material_id: str
    course_name: str
    title: str
    token: str
    qr_payload: str
    created_at: datetime
    expires_at: datetime
    is_active: bool
    summary: AttendanceSheetSummary
    students: list[AttendanceSheetStudent]
