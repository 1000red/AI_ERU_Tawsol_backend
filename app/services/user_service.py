from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User, UserType
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import hash_password, verify_password, create_access_token, create_reset_token, decode_token
from app.utils.email import send_otp_email
from app.core.config import settings
from datetime import datetime, timedelta
import random
import string

# In-memory OTP store — swap for Redis in production
_otp_store: dict[str, dict] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))



def _calculate_level(type_code: str, total_hours: int) -> int:
    if type_code != "STU":
        return 100
    if total_hours < 30:
        return 1
    elif total_hours < 60:
        return 2
    elif total_hours < 90:
        return 3
    else:
        return 4


# ── User CRUD ─────────────────────────────────────────────────────────────────

def get_user_by_id(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    return db.query(User).offset(skip).limit(limit).all()


def create_user(db: Session, data: UserCreate) -> User:
    if get_user_by_email(db, data.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.uni_code == data.uni_code).first():
        raise HTTPException(status_code=400, detail="University code already registered")

    user = User(
        uni_code=data.uni_code,
        name=data.name,
        email=data.email,
        password=hash_password(data.uni_code),  # ← الباسورد = uni_code
        total_hours=0,
        level=_calculate_level(data.type_code, 0),
        type_code=data.type_code,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def update_user(db: Session, user_id: int, data: UserUpdate) -> User:
    user = get_user_by_id(db, user_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    user.level = _calculate_level(user.type_code, user.total_hours)
    db.commit()
    db.refresh(user)
    return user


def update_total_hours(db: Session, user_id: int, total_hours: int) -> User:
    user = get_user_by_id(db, user_id)
    user.total_hours = total_hours
    user.level = _calculate_level(user.type_code, total_hours)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> None:
    user = get_user_by_id(db, user_id)
    db.delete(user)
    db.commit()


# ── Auth ──────────────────────────────────────────────────────────────────────

def login_user(db: Session, email: str, password: str) -> dict:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token({"sub": str(user.user_id), "type": user.type_code})
    return {"access_token": token, "token_type": "bearer", "user": user}


def change_password(db: Session, user_id: int, old_password: str, new_password: str) -> None:
    user = get_user_by_id(db, user_id)
    if not verify_password(old_password, user.password):
        raise HTTPException(status_code=400, detail="Old password is incorrect")
    user.password = hash_password(new_password)
    db.commit()


# ── OTP / Forgot Password ─────────────────────────────────────────────────────

def request_otp(db: Session, email: str) -> dict:
    user = get_user_by_email(db, email)
    if not user:
        return {"message": "If this email is registered, you will receive an OTP."}

    otp = _generate_otp()
    _otp_store[email] = {
        "otp": otp,
        "expires_at": datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
        "user_id": user.user_id,
    }

    sent = send_otp_email(email, otp, user.name)
    if not sent:
        raise HTTPException(status_code=500, detail="Failed to send OTP email")

    result: dict = {
        "message": f"OTP sent to {email}. Valid for {settings.OTP_EXPIRE_MINUTES} minutes."
    }
    if not settings.SENDGRID_API_KEY:
        result["debug_otp"] = otp
    return result


def verify_otp(email: str, otp: str) -> str:
    record = _otp_store.get(email)
    if not record:
        raise HTTPException(status_code=400, detail="No OTP requested for this email")
    if datetime.utcnow() > record["expires_at"]:
        del _otp_store[email]
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")
    if record["otp"] != otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    reset_token = create_reset_token(record["user_id"])
    del _otp_store[email]
    return reset_token


def reset_password(db: Session, reset_token: str, new_password: str) -> None:
    payload = decode_token(reset_token)
    if payload.get("purpose") != "reset":
        raise HTTPException(status_code=400, detail="Invalid token purpose")
    user = get_user_by_id(db, int(payload["sub"]))
    user.password = hash_password(new_password)
    db.commit()


# ── User Types ────────────────────────────────────────────────────────────────

def get_user_types(db: Session) -> list[UserType]:
    return db.query(UserType).all()