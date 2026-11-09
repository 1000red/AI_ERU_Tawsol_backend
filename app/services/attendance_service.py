import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from app.models.attendance import AttendanceSession, AttendanceRecord
from app.models.material import Material, MaterialStudent, MaterialTeacher
from app.models.user import User
from app.schemas.attendance import (
    AttendanceSessionCreate,
    AttendanceSessionOut,
    AttendanceAttendee,
    AttendanceCheckInOut,
    StudentCourseAttendanceSummary,
)


def create_attendance_session(db: Session, doctor_user: User, data: AttendanceSessionCreate) -> AttendanceSessionOut:
    # 1. Verify course exists
    mat = db.query(Material).filter(Material.material_id == data.material_id).first()
    if not mat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"المقرر الدراسي '{data.material_id}' غير موجود."
        )

    # 2. Deactivate any previous open sessions for this course created by this doctor
    db.query(AttendanceSession).filter(
        AttendanceSession.material_id == data.material_id,
        AttendanceSession.is_active == True,
    ).update({"is_active": False})

    # 3. Generate secure token and expiry
    duration = max(1, min(data.duration_minutes or 15, 120))
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=duration)
    token = f"WE-ATT-{secrets.token_urlsafe(16)}"

    session = AttendanceSession(
        material_id=data.material_id,
        created_by=doctor_user.user_id,
        title=data.title or "محاضرة",
        token=token,
        expires_at=expires_at,
        is_active=True,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # qr_payload is formatted as JSON or clean URI that mobile_scanner parses
    qr_payload = f"eru_attendance:{session.token}"

    return AttendanceSessionOut(
        session_id=session.session_id,
        material_id=session.material_id,
        course_name=mat.name,
        title=session.title,
        token=session.token,
        qr_payload=qr_payload,
        expires_at=session.expires_at,
        is_active=session.is_active,
        created_at=session.created_at,
        total_attended=0,
        attendees=[],
    )


def close_attendance_session(db: Session, session_id: int, user: User) -> AttendanceSessionOut:
    session = db.query(AttendanceSession).filter(AttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="جلسة التحضير غير موجودة.")
    session.is_active = False
    db.commit()
    return get_session_details(db, session_id)


def get_session_details(db: Session, session_id: int) -> AttendanceSessionOut:
    session = db.query(AttendanceSession).filter(AttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="جلسة التحضير غير موجودة.")

    mat = db.query(Material).filter(Material.material_id == session.material_id).first()
    records = (
        db.query(AttendanceRecord, User)
        .join(User, AttendanceRecord.student_id == User.user_id)
        .filter(AttendanceRecord.session_id == session_id)
        .order_by(AttendanceRecord.scanned_at.desc())
        .all()
    )

    attendees = [
        AttendanceAttendee(
            record_id=r.record_id,
            student_id=u.user_id,
            student_name=u.name,
            student_unicode=u.uni_code,
            scanned_at=r.scanned_at,
            status=r.status,
        )
        for r, u in records
    ]

    # Check if expired automatically
    now = datetime.now(timezone.utc)
    is_active = session.is_active and (session.expires_at > now)

    return AttendanceSessionOut(
        session_id=session.session_id,
        material_id=session.material_id,
        course_name=mat.name if mat else session.material_id,
        title=session.title,
        token=session.token,
        qr_payload=f"eru_attendance:{session.token}",
        expires_at=session.expires_at,
        is_active=is_active,
        created_at=session.created_at,
        total_attended=len(attendees),
        attendees=attendees,
    )


def student_check_in(db: Session, student_user: User, raw_token: str) -> AttendanceCheckInOut:
    # Clean token (handles raw token or eru_attendance:<token>)
    clean_token = raw_token.strip()
    if clean_token.startswith("eru_attendance:"):
        clean_token = clean_token.split(":", 1)[1]

    session = db.query(AttendanceSession).filter(AttendanceSession.token == clean_token).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="رمز الـ QR غير صالح أو جلسة التحضير غير موجودة."
        )

    now = datetime.now(timezone.utc)
    if not session.is_active or session.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="عفواً، انتهت صلاحية جلسة التحضير هذه ولم تعد تقبل تسجيل الحضور."
        )

    # Check if student is enrolled in this course
    enrollment = db.query(MaterialStudent).filter(
        MaterialStudent.material_id == session.material_id,
        MaterialStudent.user_id == student_user.user_id
    ).first()
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="أنت غير مسجل في هذا المقرر الدراسي."
        )

    # Check if already scanned
    existing = db.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == session.session_id,
        AttendanceRecord.student_id == student_user.user_id
    ).first()
    if existing:
        mat = db.query(Material).filter(Material.material_id == session.material_id).first()
        return AttendanceCheckInOut(
            message="تم تسجيل حضورك مسبقاً في هذه المحاضرة!",
            record_id=existing.record_id,
            session_id=session.session_id,
            material_id=session.material_id,
            course_name=mat.name if mat else session.material_id,
            scanned_at=existing.scanned_at,
            status=existing.status,
        )

    # Create new record
    record = AttendanceRecord(
        session_id=session.session_id,
        material_id=session.material_id,
        student_id=student_user.user_id,
        status="PRESENT",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    mat = db.query(Material).filter(Material.material_id == session.material_id).first()

    return AttendanceCheckInOut(
        message="✅ تم تسجيل حضورك بنجاح!",
        record_id=record.record_id,
        session_id=session.session_id,
        material_id=session.material_id,
        course_name=mat.name if mat else session.material_id,
        scanned_at=record.scanned_at,
        status=record.status,
    )


def get_student_attendance_summary(db: Session, student_user: User) -> list[StudentCourseAttendanceSummary]:
    # 1. Get student's enrolled courses
    enrollments = db.query(MaterialStudent, Material).join(
        Material, MaterialStudent.material_id == Material.material_id
    ).filter(MaterialStudent.user_id == student_user.user_id).all()

    summaries = []
    for enr, mat in enrollments:
        total_sessions = db.query(func.count(AttendanceSession.session_id)).filter(
            AttendanceSession.material_id == mat.material_id
        ).scalar() or 0

        attended = db.query(func.count(AttendanceRecord.record_id)).filter(
            AttendanceRecord.material_id == mat.material_id,
            AttendanceRecord.student_id == student_user.user_id,
        ).scalar() or 0

        rate = round((attended / total_sessions * 100.0), 1) if total_sessions > 0 else 100.0

        summaries.append(
            StudentCourseAttendanceSummary(
                material_id=mat.material_id,
                course_name=mat.name,
                attended_sessions=attended,
                total_sessions=total_sessions,
                attendance_rate=rate,
            )
        )

    return summaries
