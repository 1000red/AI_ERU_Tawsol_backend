from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from fastapi import HTTPException, status
from datetime import datetime, timedelta, timezone
import random
import string

from app.models.user import User
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
    user = get_user_by_email(db, email)
    if not user:
        return {"message": "If this email is registered, you will receive an OTP."}

    otp = _generate_otp()
    _otp_store[email] = {
        "otp": otp,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES),
        "user_id": user.user_id,
    }

    sent = send_otp_email(email, otp, user.name)
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP email",
        )

    result: dict = {
        "message": f"OTP sent to {email}. Valid for {OTP_EXPIRE_MINUTES} minutes."
    }
    return result


def verify_otp(email: str, otp: str) -> str:
    record = _otp_store.get(email)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OTP requested for this email"
        )
    if datetime.now(timezone.utc) > record["expires_at"]:
        del _otp_store[email]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please request a new one."
        )
    if record["otp"] != otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP"
        )

    reset_token = create_reset_token(record["user_id"])
    del _otp_store[email]
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
    if data.name is not None:
        user.name = data.name.strip()
    if data.email is not None:
        user.email = data.email.strip().lower()
    if data.uni_code is not None:
        user.uni_code = data.uni_code.strip()
    if data.type_code is not None:
        user.type_code = data.type_code.strip().upper()
    if data.level is not None:
        user.level = data.level
    if data.department is not None:
        user.department = data.department.strip() if data.department else None
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

    return stats
