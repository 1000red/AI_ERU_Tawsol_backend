from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
import re


# ── User ──────────────────────────────────────────────────────────────────────

class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class UserOut(BaseModel):
    user_id:              int
    uni_code:             str
    name:                 str
    email:                EmailStr
    type_code:            str
    level:                int = 0
    profile_picture:      Optional[str] = None
    department:           Optional[str] = None
    current_password: bool = False
    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    name: Optional[str] = None
    profile_picture: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


# ── Auth responses ────────────────────────────────────────────────────────────

class TokenOut(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserOut


# ── OTP / Password reset ──────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp:   str


class ResetPasswordRequest(BaseModel):
    reset_token:  str
    new_password: str