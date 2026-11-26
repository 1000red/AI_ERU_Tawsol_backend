from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.dependencies import get_current_user, require_staff
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
    LiveRotatingQROut,
)
from app.services import attendance_service as att_svc
from app.services import gradebook_service

router = APIRouter(prefix="/attendance", tags=["Smart Attendance"])


@router.post("/sessions", response_model=AttendanceSessionOut, status_code=status.HTTP_201_CREATED)
def create_session(
    data: AttendanceSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """(Doctor / Teacher / Admin) Create a dynamic QR attendance session for a lecture."""
    return att_svc.create_attendance_session(db, current_user, data)


@router.get("/sessions/{session_id}", response_model=AttendanceSessionOut)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """View session status and live attendee list."""
    return att_svc.get_session_details(db, session_id)


@router.get("/sessions/{session_id}/live-qr", response_model=LiveRotatingQROut)
@router.get("/session/{session_id}/live-qr", response_model=LiveRotatingQROut)
def get_session_live_qr(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """(Teacher) Get dynamic rotating anti-proxy QR code token and TTL (changes every 25 seconds)."""
    return att_svc.get_live_rotating_qr(db, session_id)


@router.get("/sessions/{session_id}/sheet", response_model=AttendanceSheetOut)
def get_attendance_sheet(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """(Teacher / Admin) Get full attendance sheet with all enrolled students and their status."""
    return att_svc.get_session_attendance_sheet(db, session_id)


@router.post("/sessions/{session_id}/mark", response_model=AttendanceSheetOut)
def mark_attendance(
    session_id: int,
    data: AttendanceMarkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """(Teacher / Admin) Manually mark or change a student's attendance status."""
    return att_svc.mark_student_attendance(db, session_id, data.student_id, data.status)


@router.post("/sessions/{session_id}/batch-mark", response_model=AttendanceSheetOut)
def batch_mark_attendance(
    session_id: int,
    data: AttendanceBatchMarkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """(Teacher / Admin) Bulk mark or update student attendance statuses."""
    return att_svc.batch_mark_attendance(db, session_id, data.records)


@router.get("/courses/{material_id}/sessions")
def get_course_sessions(
    material_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """(Teacher / Admin) List previous attendance sessions for a course."""
    return att_svc.get_course_attendance_sessions(db, material_id)


@router.get("/courses/{material_id}/export-gradebook")
@router.get("/courses/{material_id}/gradebook/export-excel")
def export_course_gradebook_excel(
    material_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """(Teacher / Admin) Export official Egyptian Ministry of Education / WE ATS Gradebook (.xlsx)."""
    excel_bytes, filename = gradebook_service.generate_course_gradebook_excel(db, material_id)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/courses/{material_id}/analytics/weakness-heatmap")
def get_course_weakness_heatmap(
    material_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """(Teacher / Admin) Get classroom competency & weakness heatmap for targeted pedagogical remediation."""
    return gradebook_service.get_classroom_weakness_heatmap(db, material_id)


@router.post("/sessions/{session_id}/close", response_model=AttendanceSessionOut)
def close_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
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


@router.get("/public-summary/{student_identifier}", response_model=list[StudentCourseAttendanceSummary])
def public_student_attendance_summary(
    student_identifier: str,
    db: Session = Depends(get_db),
):
    """(Student Web Scanner) View attendance percentage across all enrolled courses using student code or email."""
    from sqlalchemy import func
    ident = student_identifier.strip()
    filters = [
        func.lower(User.email) == ident.lower(),
        func.lower(User.uni_code) == ident.lower(),
    ]
    if ident.isdigit():
        filters.append(User.user_id == int(ident))

    from sqlalchemy import or_
    user = db.query(User).filter(or_(*filters)).first()
    if not user:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail=f"لم يتم العثور على طالب بالمعرف '{student_identifier}'. يرجى التحقق من كود الطالب أو البريد."
        )
    return att_svc.get_student_attendance_summary(db, user)

