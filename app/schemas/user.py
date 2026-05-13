from pydantic import BaseModel, EmailStr, field_validator, model_validator
from typing import Optional
# import re


# ── UserType ──────────────────────────────────────────────────────────────────

class UserTypeBase(BaseModel):
    code:        str
    description: str


class UserTypeOut(UserTypeBase):
    # convert ORM to JSON
    model_config = {"from_attributes": True} 


# ── User ──────────────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    uni_code:    str
    name:        str
    email:       EmailStr
    type_code:   str
    total_hours: int = 0


class UserCreate(UserBase):
    pass


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class UserOut(UserBase):
    user_id: int
    level:   int = 0
    profile_picture: Optional[str] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def calculate_level(self) -> "UserOut":
        if self.type_code != "STU":
            self.level = 100
        elif self.total_hours < 30:
            self.level = 1
        elif self.total_hours < 60:
            self.level = 2
        elif self.total_hours < 90:
            self.level = 3
        else:
            self.level = 4
        return self


class UserUpdate(BaseModel):
    name: Optional[str] = None
    profile_picture: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class UpdateHoursRequest(BaseModel):
    total_hours: int

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
        
        # # 2. Number Check
        # if not re.search(r"\d", v):
        #     raise ValueError("Password must contain at least one number")
        
        # # 3. Uppercase & Lowercase Check
        # if not re.search(r"[A-Z]", v) or not re.search(r"[a-z]", v):
        #     raise ValueError("Password must contain both uppercase and lowercase letters")
        
        # # 4. Special Character Check
        # if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
        #     raise ValueError("Password must contain at least one special character (e.g., @, #, $, %)")
            
        return v