from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ComplaintCreate(BaseModel):
    material_id:    int
    student_id:     int
    teacher_id:     int
    complaint_text: str


class ComplaintOut(BaseModel):
    complaint_id:   int
    material_id:    int
    student_id:     int
    teacher_id:     int
    complaint_text: str
    send_at:        datetime

    model_config = {"from_attributes": True}
