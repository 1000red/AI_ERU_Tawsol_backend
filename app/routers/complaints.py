from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.models.complaint import Complaint
from app.schemas.complaint import ComplaintCreate, ComplaintOut

router = APIRouter(prefix="/complaints", tags=["Complaints"])


@router.post("/", response_model=ComplaintOut, status_code=201)
def create_complaint(data: ComplaintCreate, db: Session = Depends(get_db)):
    complaint = Complaint(**data.model_dump(), send_at=datetime.utcnow())
    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    return complaint


@router.get("/student/{student_id}", response_model=list[ComplaintOut])
def student_complaints(student_id: int, db: Session = Depends(get_db)):
    return db.query(Complaint).filter(Complaint.student_id == student_id).all()


@router.get("/teacher/{teacher_id}", response_model=list[ComplaintOut])
def teacher_complaints(teacher_id: int, db: Session = Depends(get_db)):
    return db.query(Complaint).filter(Complaint.teacher_id == teacher_id).all()


@router.get("/material/{material_id}", response_model=list[ComplaintOut])
def material_complaints(material_id: int, db: Session = Depends(get_db)):
    return db.query(Complaint).filter(Complaint.material_id == material_id).all()


@router.delete("/{complaint_id}", status_code=204)
def delete_complaint(
    complaint_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if not complaint:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Complaint not found")
    db.delete(complaint)
    db.commit()
