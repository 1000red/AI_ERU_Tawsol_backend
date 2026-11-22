import os
import secrets
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.user import (
    UserLogin, TokenOut,
    ForgotPasswordRequest, VerifyOTPRequest, ResetPasswordRequest,
)
from app.services import user_service as svc

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenOut)
def login(data: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.headers.get("x-forwarded-for")
    if ip:
        ip = ip.split(",")[0].strip()
    elif request.client:
        ip = request.client.host
    user_agent = request.headers.get("user-agent")

    result = svc.login_user(db, data.email, data.password, ip=ip, user_agent=user_agent)

    # Issue CSRF token
    csrf_token = secrets.token_urlsafe(32)
    result["csrf_token"] = csrf_token

    # Determine secure cookie flag
    is_secure = request.url.scheme == "https" or os.getenv("ENVIRONMENT") == "production"

    # Set HttpOnly session cookie
    response.set_cookie(
        key="admin_token",
        value=result["access_token"],
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=1800,  # 30 minutes
        path="/",
    )
    # Set CSRF token cookie (accessible by browser JavaScript)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=is_secure,
        samesite="lax",
        max_age=1800,
        path="/",
    )
    return result


@router.get("/login", include_in_schema=False)
def auth_login_page(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept or "application/xhtml" in accept or "*/*" in accept or not accept:
        from app.routers.user_management_web import USER_MANAGEMENT_HTML
        return HTMLResponse(content=USER_MANAGEMENT_HTML)
    return {"message": "Use POST /auth/login for authentication."}


@router.post("/logout")
def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    auth = request.headers.get("authorization")
    token = auth.split(" ")[1] if auth and auth.startswith("Bearer ") else request.cookies.get("admin_token")
    if token:
        try:
            from app.core.security import decode_token
            from app.services.admin_audit_service import admin_audit_service
            payload = decode_token(token)
            user_id = int(payload.get("sub", 0))
            if payload.get("type") == "ADM":
                admin_audit_service.log_action(
                    db,
                    action="LOGOUT",
                    admin_id=user_id,
                    target_resource="auth:logout",
                    ip_address=request.headers.get("x-forwarded-for") or (request.client.host if request.client else None),
                    user_agent=request.headers.get("user-agent"),
                    details="Admin logged out",
                )
        except Exception:
            pass

    response.delete_cookie(key="admin_token", path="/")
    response.delete_cookie(key="csrf_token", path="/")
    return {"message": "Logged out successfully"}


# ── OTP / Password reset ──────────────────────────────────────────────────────

@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    return svc.request_otp(db, data.email)


@router.post("/verify-otp")
def verify_otp(data: VerifyOTPRequest, db: Session = Depends(get_db)):
    reset_token = svc.verify_otp(db, data.email, data.otp)
    return {"message": "OTP verified.", "reset_token": reset_token}


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    svc.reset_password(db, data.reset_token, data.new_password)
    return {"message": "Password reset successfully. You can now log in."}