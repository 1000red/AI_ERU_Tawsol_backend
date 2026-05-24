from pydantic import BaseModel, model_validator
from typing import Optional, Any


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
    student_count:   int = 0
    content_count:   int = 0
    teacher_name:    Optional[str] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def extract_teacher_name(cls, data: Any) -> Any:
        if hasattr(data, "teacher_assignments") and data.teacher_assignments:
            first = data.teacher_assignments[0]
            if hasattr(first, "teacher") and first.teacher:
                data.__dict__["teacher_name"] = first.teacher.name
        return data


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