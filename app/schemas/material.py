from pydantic import BaseModel
from typing import Optional


class MaterialBase(BaseModel):
    name:            str
    description:     Optional[str] = None
    duration:        int
    profile_picture: Optional[str] = None


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(MaterialBase):
    name:        Optional[str] = None
    duration:    Optional[int] = None


class MaterialOut(MaterialBase):
    material_id: int
    model_config = {"from_attributes": True}


# ── Enrollment / Assignment ───────────────────────────────────────────────────

class EnrollStudentIn(BaseModel):
    material_id: int
    user_id:     int


class AssignTeacherIn(BaseModel):
    material_id: int
    user_id:     int


class EnrollmentOut(BaseModel):
    id:          int
    material_id: int
    user_id:     int
    model_config = {"from_attributes": True}