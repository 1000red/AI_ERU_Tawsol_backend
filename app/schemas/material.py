from pydantic import BaseModel, Field, model_validator
from typing import Optional, Any


class MaterialOut(BaseModel):
    material_id:     str
    name:            str
    description:     Optional[str] = None
    duration:        Optional[int] = 0
    student_count:   Optional[int] = 0
    content_count:   Optional[int] = 0
    teacher_name:    Optional[str] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def extract_data(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {
                "material_id": str(data.get("material_id") or ""),
                "name": str(data.get("name") or ""),
                "description": data.get("description"),
                "duration": data.get("duration") or 0,
                "student_count": data.get("student_count") or 0,
                "content_count": data.get("content_count") or 0,
                "teacher_name": data.get("teacher_name"),
            }

        teacher_name = None
        if hasattr(data, "teacher_assignments") and data.teacher_assignments:
            first = data.teacher_assignments[0]
            if hasattr(first, "teacher") and first.teacher:
                teacher_name = first.teacher.name

        return {
            "material_id": getattr(data, "material_id", ""),
            "name": getattr(data, "name", ""),
            "description": getattr(data, "description", None),
            "duration": getattr(data, "duration", 0) or 0,
            "student_count": getattr(data, "student_count", 0) or 0,
            "content_count": getattr(data, "content_count", 0) or 0,
            "teacher_name": teacher_name,
        }


class MaterialCreate(BaseModel):
    material_id: str = Field(..., min_length=1)
    name:        str
    description: Optional[str] = None
    duration:    Optional[int] = 0
    teacher_id:  Optional[int] = None


class MaterialUpdate(BaseModel):
    name:        Optional[str] = None
    description: Optional[str] = None
    duration:    Optional[int] = None


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
