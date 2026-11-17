from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.attendance import (
    AttendanceSessionCreate,
    AttendanceSessionOut,
    AttendanceCheckInRequest,
    AttendancePublicCheckInRequest,
    AttendanceCheckInOut,
    StudentCourseAttendanceSummary,
    AttendanceSheetOut,
    AttendanceMarkRequest,
    AttendanceBatchMarkRequest,
)
from app.services import attendance_service as att_svc

router = APIRouter(prefix="/attendance", tags=["Smart Attendance"])


@router.post("/sessions", response_model=AttendanceSessionOut, status_code=status.HTTP_201_CREATED)
def create_session(
    data: AttendanceSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """(Doctor / Teacher / Admin) Create a dynamic QR attendance session for a lecture."""
    return att_svc.create_attendance_session(db, current_user, data)


@router.get("/sessions/{session_id}", response_model=AttendanceSessionOut)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """View session status and live attendee list."""
    return att_svc.get_session_details(db, session_id)


@router.get("/sessions/{session_id}/sheet", response_model=AttendanceSheetOut)
def get_attendance_sheet(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """(Teacher / Admin) Get full attendance sheet with all enrolled students and their status."""
    return att_svc.get_session_attendance_sheet(db, session_id)


@router.post("/sessions/{session_id}/mark", response_model=AttendanceSheetOut)
def mark_attendance(
    session_id: int,
    data: AttendanceMarkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """(Teacher / Admin) Manually mark or change a student's attendance status."""
    return att_svc.mark_student_attendance(db, session_id, data.student_id, data.status)


@router.post("/sessions/{session_id}/batch-mark", response_model=AttendanceSheetOut)
def batch_mark_attendance(
    session_id: int,
    data: AttendanceBatchMarkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """(Teacher / Admin) Bulk mark or update student attendance statuses."""
    return att_svc.batch_mark_attendance(db, session_id, data.records)


@router.get("/courses/{material_id}/sessions")
def get_course_sessions(
    material_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """(Teacher / Admin) List previous attendance sessions for a course."""
    return att_svc.get_course_attendance_sessions(db, material_id)


@router.post("/sessions/{session_id}/close", response_model=AttendanceSessionOut)
def close_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually terminate and lock an attendance session."""
    return att_svc.close_attendance_session(db, session_id, current_user)


@router.post("/check-in", response_model=AttendanceCheckInOut)
def student_check_in(
    data: AttendanceCheckInRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """(Student) Submit scanned QR code token to record presence."""
    return att_svc.student_check_in(db, current_user, data.token)


@router.post("/public-check-in", response_model=AttendanceCheckInOut)
def public_student_check_in(
    data: AttendancePublicCheckInRequest,
    db: Session = Depends(get_db),
):
    """(Student Web Scanner) Check in using student ID/code/email and session token."""
    return att_svc.student_public_check_in(db, data.token, data.student_identifier)


@router.get("/my-summary", response_model=list[StudentCourseAttendanceSummary])
def my_attendance_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """(Student) View attendance percentage across all enrolled courses."""
    return att_svc.get_student_attendance_summary(db, current_user)
