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
    AttendanceSheetOut,
    AttendanceSheetStudent,
    AttendanceSheetSummary,
    AttendanceMarkRequest,
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
            scanned_at=existing.scanned_at or datetime.now(timezone.utc),
            status=existing.status,
            success=True,
            student_name=student_user.name,
            student_uni_code=student_user.uni_code or f"STU-{student_user.user_id}",
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
        scanned_at=record.scanned_at or datetime.now(timezone.utc),
        status=record.status,
        success=True,
        student_name=student_user.name,
        student_uni_code=student_user.uni_code or f"STU-{student_user.user_id}",
    )


def student_public_check_in(db: Session, raw_token: str, student_identifier: str) -> AttendanceCheckInOut:
    """Public / camera scan check-in by student code, email, or user_id."""
    clean_id = student_identifier.strip()
    student = None

    if clean_id.isdigit():
        student = db.query(User).filter(User.user_id == int(clean_id), User.type_code == "STU").first()

    if not student:
        student = db.query(User).filter(
            func.lower(User.uni_code) == clean_id.lower(),
            User.type_code == "STU"
        ).first()

    if not student:
        student = db.query(User).filter(
            func.lower(User.email) == clean_id.lower(),
            User.type_code == "STU"
        ).first()

    if not student:
        student = db.query(User).filter(
            User.name.ilike(f"%{clean_id}%"),
            User.type_code == "STU"
        ).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="لم يتم العثور على طالب بهذا الكود أو البريد الإلكتروني. يرجى التأكد من كتابة كود الطالب بدقة."
        )

    return student_check_in(db, student, raw_token)


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


# ── Full Attendance Sheet & Manual Filling Services ─────────────────────────
def get_session_attendance_sheet(db: Session, session_id: int) -> AttendanceSheetOut:
    session = db.query(AttendanceSession).filter(AttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="جلسة التحضير غير موجودة.")

    mat = db.query(Material).filter(Material.material_id == session.material_id).first()
    course_name = mat.name if mat else session.material_id

    # 1. Fetch all enrolled students in this course
    enrolled_students = (
        db.query(User)
        .join(MaterialStudent, MaterialStudent.user_id == User.user_id)
        .filter(MaterialStudent.material_id == session.material_id)
        .order_by(User.name.asc())
        .all()
    )

    # 2. Fetch all existing attendance records for this session
    records = db.query(AttendanceRecord).filter(AttendanceRecord.session_id == session_id).all()
    record_map = {r.student_id: r for r in records}

    # 3. Assemble full student list with accurate status
    students_out: list[AttendanceSheetStudent] = []
    present_cnt = 0
    late_cnt = 0
    excused_cnt = 0
    absent_cnt = 0

    for stu in enrolled_students:
        rec = record_map.get(stu.user_id)
        if rec:
            st = rec.status.upper()
            if st == "PRESENT":
                present_cnt += 1
            elif st == "LATE":
                late_cnt += 1
            elif st == "EXCUSED":
                excused_cnt += 1
            else:
                absent_cnt += 1
            students_out.append(
                AttendanceSheetStudent(
                    student_id=stu.user_id,
                    name=stu.name,
                    uni_code=stu.uni_code,
                    email=stu.email,
                    status=st,
                    scanned_at=rec.scanned_at,
                    record_id=rec.record_id,
                )
            )
        else:
            absent_cnt += 1
            students_out.append(
                AttendanceSheetStudent(
                    student_id=stu.user_id,
                    name=stu.name,
                    uni_code=stu.uni_code,
                    email=stu.email,
                    status="ABSENT",
                    scanned_at=None,
                    record_id=None,
                )
            )

    total_enrolled = len(enrolled_students)
    att_rate = round(((present_cnt + late_cnt) / total_enrolled * 100.0), 1) if total_enrolled > 0 else 0.0

    now = datetime.now(timezone.utc)
    is_active = session.is_active and (session.expires_at > now)

    summary = AttendanceSheetSummary(
        total_enrolled=total_enrolled,
        present_count=present_cnt,
        late_count=late_cnt,
        excused_count=excused_cnt,
        absent_count=absent_cnt,
        attendance_rate=att_rate,
    )

    return AttendanceSheetOut(
        session_id=session.session_id,
        material_id=session.material_id,
        course_name=course_name,
        title=session.title,
        token=session.token,
        qr_payload=f"eru_attendance:{session.token}",
        created_at=session.created_at,
        expires_at=session.expires_at,
        is_active=is_active,
        summary=summary,
        students=students_out,
    )


def mark_student_attendance(db: Session, session_id: int, student_id: int, status_code: str) -> AttendanceSheetOut:
    session = db.query(AttendanceSession).filter(AttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="جلسة التحضير غير موجودة.")

    clean_status = status_code.upper().strip()
    if clean_status not in ("PRESENT", "LATE", "EXCUSED", "ABSENT"):
        raise HTTPException(status_code=422, detail="حالة الحضور غير صالحة. اختر بين: PRESENT, LATE, EXCUSED, ABSENT")

    rec = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.session_id == session_id, AttendanceRecord.student_id == student_id)
        .first()
    )

    if clean_status == "ABSENT":
        if rec:
            db.delete(rec)
            db.commit()
    else:
        if rec:
            rec.status = clean_status
        else:
            rec = AttendanceRecord(
                session_id=session_id,
                material_id=session.material_id,
                student_id=student_id,
                status=clean_status,
            )
            db.add(rec)
        db.commit()

    return get_session_attendance_sheet(db, session_id)


def batch_mark_attendance(db: Session, session_id: int, records_data: list[AttendanceMarkRequest]) -> AttendanceSheetOut:
    session = db.query(AttendanceSession).filter(AttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="جلسة التحضير غير موجودة.")

    for item in records_data:
        clean_status = item.status.upper().strip()
        rec = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.session_id == session_id, AttendanceRecord.student_id == item.student_id)
            .first()
        )
        if clean_status == "ABSENT":
            if rec:
                db.delete(rec)
        elif clean_status in ("PRESENT", "LATE", "EXCUSED"):
            if rec:
                rec.status = clean_status
            else:
                rec = AttendanceRecord(
                    session_id=session_id,
                    material_id=session.material_id,
                    student_id=item.student_id,
                    status=clean_status,
                )
                db.add(rec)

    db.commit()
    return get_session_attendance_sheet(db, session_id)


def get_course_attendance_sessions(db: Session, material_id: str) -> list[dict]:
    sessions = (
        db.query(AttendanceSession)
        .filter(AttendanceSession.material_id == material_id)
        .order_by(AttendanceSession.created_at.desc())
        .limit(30)
        .all()
    )
    now = datetime.now(timezone.utc)
    results = []
    for s in sessions:
        attended = db.query(func.count(AttendanceRecord.record_id)).filter(AttendanceRecord.session_id == s.session_id).scalar() or 0
        is_active = s.is_active and (s.expires_at > now)
        results.append({
            "session_id": s.session_id,
            "material_id": s.material_id,
            "title": s.title,
            "token": s.token,
            "qr_payload": f"eru_attendance:{s.token}",
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            "is_active": is_active,
            "total_attended": attended,
        })
    return results
