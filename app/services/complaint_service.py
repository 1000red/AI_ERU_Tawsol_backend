from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.complaint import Complaint
from app.schemas.complaint import ComplaintCreate


def create_complaint(db: Session, data: ComplaintCreate) -> Complaint:
    complaint = Complaint(**data.model_dump(), send_at=datetime.now(timezone.utc))
    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    return complaint


def get_by_student(db: Session, student_id: int) -> list[Complaint]:
    return db.query(Complaint).filter(Complaint.student_id == student_id).all()


def get_by_teacher(db: Session, teacher_id: int) -> list[Complaint]:
    return db.query(Complaint).filter(Complaint.teacher_id == teacher_id).all()


def get_by_material(db: Session, material_id: int) -> list[Complaint]:
    return db.query(Complaint).filter(Complaint.material_id == material_id).all()


def delete_complaint(db: Session, complaint_id: int) -> None:
    complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    db.delete(complaint)
    db.commit()
