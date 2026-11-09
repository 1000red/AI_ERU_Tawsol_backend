from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from fastapi import HTTPException, status
from datetime import datetime, timedelta, timezone
import random
import string

from app.models.user import User
from app.models.password_reset_otp import PasswordResetOTP
from app.schemas.user import UserUpdate
from app.core.security import hash_password, verify_password, create_access_token, create_reset_token, decode_token
from app.utils.email import send_otp_email, send_welcome_email, send_password_changed_email
from app.core.config import OTP_EXPIRE_MINUTES, settings


_otp_store: dict[str, dict] = {}


def _generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


# ── User CRUD ─────────────────────────────────────────────────────────────────

def get_user_by_id(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User not found"
        )
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    cleaned = (email or '').strip().lower()
    return db.query(User).filter(
        or_(
            func.lower(User.email) == cleaned,
            func.lower(User.uni_code) == cleaned
        )
    ).first()


def update_user(db: Session, user_id: int, data: UserUpdate) -> User:
    user = get_user_by_id(db, user_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


# ── Auth ──────────────────────────────────────────────────────────────────────

def login_user(db: Session, email: str, password: str) -> dict:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token({"sub": str(user.user_id), "type": user.type_code})
    send_welcome_email(user.email, user.name)
    return {"access_token": token, "token_type": "bearer", "user": user}


def change_password(db: Session, user_id: int, old_password: str, new_password: str) -> None:
    user = get_user_by_id(db, user_id)
    if not verify_password(old_password, user.password):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Old password is incorrect"
        )
    user.password = hash_password(new_password)
    user.current_password = False
    db.commit()
    send_password_changed_email(user.email, user.name)


# ── OTP / Password ─────────────────────────────────────────────────────

def request_otp(db: Session, email: str) -> dict:
    cleaned = (email or "").strip().lower()
    user = get_user_by_email(db, cleaned)
    if not user:
        return {
            "message": "If this account is registered, you will receive an OTP code.",
            "email": cleaned,
            "expires_in_minutes": OTP_EXPIRE_MINUTES,
            "otp_sent": False
        }

    # Invalidate prior unused OTPs for this user
    db.query(PasswordResetOTP).filter(
        PasswordResetOTP.user_id == user.user_id,
        PasswordResetOTP.is_used == False
    ).update({"is_used": True})

    otp = _generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)
    
    otp_record = PasswordResetOTP(
        user_id=user.user_id,
        email=user.email,
        otp_code=otp,
        expires_at=expires_at,
        is_used=False
    )
    db.add(otp_record)
    db.commit()

    # Attempt to send email via SMTP gracefully without crashing if SMTP is unconfigured/fails
    email_sent = False
    try:
        email_sent = send_otp_email(user.email, otp, user.name)
    except Exception as e:
        print(f"[OTP] Could not deliver email via SMTP: {e}")

    result: dict = {
        "message": f"OTP sent to {user.email}. Valid for {OTP_EXPIRE_MINUTES} minutes.",
        "email": user.email,
        "expires_in_minutes": OTP_EXPIRE_MINUTES,
        "otp_sent": bool(email_sent),
        "otp_debug": otp
    }
    return result


def verify_otp(db: Session, email: str, otp: str) -> str:
    cleaned = (email or "").strip().lower()
    cleaned_otp = (otp or "").strip()
    
    # Locate user by email or student code
    user = get_user_by_email(db, cleaned)
    user_id = user.user_id if user else None

    now_utc = datetime.now(timezone.utc)
    query = db.query(PasswordResetOTP).filter(
        PasswordResetOTP.is_used == False,
        PasswordResetOTP.expires_at > now_utc
    )
    if user_id:
        query = query.filter(or_(PasswordResetOTP.user_id == user_id, func.lower(PasswordResetOTP.email) == cleaned))
    else:
        query = query.filter(func.lower(PasswordResetOTP.email) == cleaned)

    record = query.order_by(PasswordResetOTP.created_at.desc()).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid OTP requested for this email or OTP has expired. Please request a new one."
        )

    if record.otp_code != cleaned_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP"
        )

    record.is_used = True
    db.commit()

    reset_token = create_reset_token(record.user_id)
    return reset_token


def reset_password(db: Session, reset_token: str, new_password: str) -> None:
    payload = decode_token(reset_token)
    if payload.get("purpose") != "reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token purpose"
        )
    user = get_user_by_id(db, int(payload["sub"]))
    user.password = hash_password(new_password)
    user.current_password = False
    db.commit()



# ── Admin User Management & Dashboard Services ───────────────────────────────

def list_all_users(
    db: Session,
    search: str | None = None,
    role: str | None = None,
    department: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[User]:
    query = db.query(User)
    if role:
        query = query.filter(User.type_code == role.strip().upper())
    if department:
        query = query.filter(User.department.ilike(f"%{department.strip()}%"))
    if search:
        s = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(User.name).like(s),
                func.lower(User.email).like(s),
                func.lower(User.uni_code).like(s),
            )
        )
    return query.order_by(User.user_id).offset(offset).limit(limit).all()


def create_user_admin(db: Session, data) -> User:
    # check email or uni_code unique
    existing = db.query(User).filter(
        or_(
            func.lower(User.email) == data.email.strip().lower(),
            func.lower(User.uni_code) == data.uni_code.strip().lower()
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with this email ({data.email}) or university code ({data.uni_code}) already exists."
        )

    user = User(
        uni_code=data.uni_code.strip(),
        name=data.name.strip(),
        email=data.email.strip().lower(),
        password=hash_password(data.password),
        type_code=data.type_code.strip().upper(),
        level=data.level or 0,
        department=data.department.strip() if data.department else None,
        current_password=bool(data.current_password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user_admin(db: Session, user_id: int, data) -> User:
    user = get_user_by_id(db, user_id)
    
    if data.name is not None and data.name.strip():
        user.name = data.name.strip()
        
    if data.email is not None and data.email.strip():
        new_email = data.email.strip().lower()
        if new_email != user.email.lower():
            existing = db.query(User).filter(func.lower(User.email) == new_email, User.user_id != user_id).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"البريد الإلكتروني ({new_email}) مستخدم بالفعل من قبل حساب آخر."
                )
            user.email = new_email
            
    if data.uni_code is not None and data.uni_code.strip():
        new_code = data.uni_code.strip()
        if new_code != user.uni_code:
            existing = db.query(User).filter(func.lower(User.uni_code) == new_code.lower(), User.user_id != user_id).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"الكود التعريفي ({new_code}) مستخدم بالفعل من قبل حساب آخر."
                )
            user.uni_code = new_code
            
    if data.type_code is not None and data.type_code.strip():
        user.type_code = data.type_code.strip().upper()
        
    if data.level is not None:
        user.level = data.level
        
    if data.department is not None:
        dept = data.department.strip()
        user.department = dept if dept else None
        
    if hasattr(data, "password") and data.password and len(data.password.strip()) >= 4:
        user.password = hash_password(data.password.strip())
        user.current_password = False
        
    if data.current_password is not None:
        user.current_password = bool(data.current_password)

    db.commit()
    db.refresh(user)
    return user


def reset_password_admin(db: Session, user_id: int, new_password: str) -> None:
    user = get_user_by_id(db, user_id)
    if not new_password or len(new_password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 4 characters long."
        )
    user.password = hash_password(new_password)
    user.current_password = False
    db.commit()


def delete_user_admin(db: Session, user_id: int) -> None:
    user = get_user_by_id(db, user_id)
    # clean up foreign key references if any
    from app.models.material import MaterialStudent, MaterialTeacher
    db.query(MaterialStudent).filter(MaterialStudent.user_id == user_id).delete(synchronize_session=False)
    db.query(MaterialTeacher).filter(MaterialTeacher.user_id == user_id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


def get_dashboard_stats(db: Session) -> dict:
    stats = {
        "total_users": 0,
        "students_count": 0,
        "doctors_count": 0,
        "admins_count": 0,
        "courses_count": 0,
        "announcements_count": 0,
        "assignments_count": 0,
        "files_count": 0,
        "messages_count": 0,
        "status": "healthy"
    }
    try:
        stats["total_users"] = db.query(func.count(User.user_id)).scalar() or 0
        stats["students_count"] = db.query(func.count(User.user_id)).filter(User.type_code == "STU").scalar() or 0
        stats["doctors_count"] = db.query(func.count(User.user_id)).filter(User.type_code == "DR").scalar() or 0
        stats["admins_count"] = db.query(func.count(User.user_id)).filter(User.type_code == "ADM").scalar() or 0
    except Exception as e:
        print("[Stats] Error querying users:", e)

    try:
        from app.models.material import Material
        stats["courses_count"] = db.query(func.count(Material.material_id)).scalar() or 0
    except Exception as e:
        print("[Stats] Error querying material:", e)

    try:
        from app.models.content.announcement import Announcement
        stats["announcements_count"] = db.query(func.count(Announcement.announcement_id)).scalar() or 0
    except Exception as e:
        pass

    try:
        from app.models.content.assignment import Assignment
        stats["assignments_count"] = db.query(func.count(Assignment.assignment_id)).scalar() or 0
    except Exception as e:
        pass

    try:
        from app.models.content.material_file import MaterialFile
        stats["files_count"] = db.query(func.count(MaterialFile.file_id)).scalar() or 0
    except Exception as e:
        pass

    try:
        from app.models.chat import ChatHistory
        stats["messages_count"] = db.query(func.count(ChatHistory.chat_id)).scalar() or 0
    except Exception as e:
        pass

    try:
        from app.models.attendance import AttendanceRecord
        stats["attendance_records_count"] = db.query(func.count(AttendanceRecord.record_id)).scalar() or 0
    except Exception as e:
        pass

    return stats
