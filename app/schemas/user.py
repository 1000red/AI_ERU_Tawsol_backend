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
    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    name: Optional[str] = None
    profile_picture: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
         # 1. Length Check
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        # 2. Number Check
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        
        # 3. Uppercase & Lowercase Check
        if not re.search(r"[A-Z]", v) or not re.search(r"[a-z]", v):
            raise ValueError("Password must contain both uppercase and lowercase letters")
        
        # 4. Special Character Check
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character (e.g., @, #, $, %)")
            
        return v


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

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        # 1. Length Check
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        # 2. Number Check
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        
        # 3. Uppercase & Lowercase Check
        if not re.search(r"[A-Z]", v) or not re.search(r"[a-z]", v):
            raise ValueError("Password must contain both uppercase and lowercase letters")
        
        # 4. Special Character Check
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character (e.g., @, #, $, %)")
            
        return v