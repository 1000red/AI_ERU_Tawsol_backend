from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.security import bearer_scheme, decode_token, blacklist_token
from app.schemas.user import (
    UserLogin, TokenOut,
    ForgotPasswordRequest, VerifyOTPRequest, ResetPasswordRequest,
)
from app.services import user_service as svc

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenOut)
def login(data: UserLogin, db: Session = Depends(get_db)):
    return svc.login_user(db, data.email, data.password)


@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    payload = decode_token(credentials.credentials)
    blacklist_token(db, payload)
    return {"message": "Logged out successfully"}


# ── OTP / Password reset ──────────────────────────────────────────────────────

@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    return svc.request_otp(db, data.email)


@router.post("/verify-otp")
def verify_otp(data: VerifyOTPRequest):
    reset_token = svc.verify_otp(data.email, data.otp)
    return {"message": "OTP verified.", "reset_token": reset_token}


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    svc.reset_password(db, data.reset_token, data.new_password)
    return {"message": "Password reset successfully. You can now log in."}