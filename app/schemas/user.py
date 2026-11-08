from pydantic import BaseModel
from typing import Optional


# ── User ──────────────────────────────────────────────────────────────────────

class UserLogin(BaseModel):
    email:    str
    password: str


class UserOut(BaseModel):
    user_id:          int
    uni_code:         str
    name:             str
    email:            str
    type_code:        str
    level:            int = 0
    department:       Optional[str] = None
    current_password: bool = False
    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    name: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


# ── Admin User Management Schemas ─────────────────────────────────────────────

class AdminUserCreate(BaseModel):
    uni_code:         str
    name:             str
    email:            str
    password:         str
    type_code:        str = "STU" # "STU", "DR", "ADM"
    level:            Optional[int] = 3
    department:       Optional[str] = None
    current_password: Optional[bool] = False


class AdminUserUpdate(BaseModel):
    uni_code:         Optional[str] = None
    name:             Optional[str] = None
    email:            Optional[str] = None
    type_code:        Optional[str] = None
    level:            Optional[int] = None
    department:       Optional[str] = None
    current_password: Optional[bool] = None


class AdminPasswordReset(BaseModel):
    new_password: str


# ── Auth responses ────────────────────────────────────────────────────────────

class TokenOut(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserOut


# ── OTP / Password reset ──────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: str


class VerifyOTPRequest(BaseModel):
    email: str
    otp:   str


class ResetPasswordRequest(BaseModel):
    reset_token:  str
    new_password: str
