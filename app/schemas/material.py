from pydantic import BaseModel
from typing import Optional


class MaterialCreate(BaseModel):
    material_id:     str
    name:            str
    description:     Optional[str] = None
    duration:        int = 0
    profile_picture: Optional[str] = None


class MaterialUpdate(BaseModel):
    name:            Optional[str] = None
    description:     Optional[str] = None
    duration:        Optional[int] = None
    profile_picture: Optional[str] = None


class MaterialOut(BaseModel):
    material_id:     str
    name:            str
    description:     Optional[str] = None
    duration:        int
    profile_picture: Optional[str] = None
    model_config = {"from_attributes": True}


class EnrollStudentIn(BaseModel):
    material_id: str
    user_id:     int


class AssignTeacherIn(BaseModel):
    material_id: str
    user_id:     int


class EnrollmentOut(BaseModel):
    id:          int
    material_id: str
    user_id:     int
    model_config = {"from_attributes": True}