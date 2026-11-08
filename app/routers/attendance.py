from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.attendance import (
    AttendanceSessionCreate,
    AttendanceSessionOut,
    AttendanceCheckInRequest,
    AttendanceCheckInOut,
    StudentCourseAttendanceSummary,
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


@router.get("/my-summary", response_model=list[StudentCourseAttendanceSummary])
def my_attendance_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """(Student) View attendance percentage across all enrolled courses."""
    return att_svc.get_student_attendance_summary(db, current_user)
