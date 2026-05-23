from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.schemas.complaint import ComplaintCreate, ComplaintOut
from app.services import complaint_service as svc

router = APIRouter(prefix="/complaints", tags=["Complaints"])


@router.post("/", response_model=ComplaintOut, status_code=201)
def create_complaint(data: ComplaintCreate, db: Session = Depends(get_db)):
    return svc.create_complaint(db, data)


@router.get("/student/{student_id}", response_model=list[ComplaintOut])
def student_complaints(student_id: int, db: Session = Depends(get_db)):
    return svc.get_by_student(db, student_id)


@router.get("/teacher/{teacher_id}", response_model=list[ComplaintOut])
def teacher_complaints(teacher_id: int, db: Session = Depends(get_db)):
    return svc.get_by_teacher(db, teacher_id)


@router.get("/material/{material_id}", response_model=list[ComplaintOut])
def material_complaints(material_id: int, db: Session = Depends(get_db)):
    return svc.get_by_material(db, material_id)


@router.delete("/{complaint_id}", status_code=204)
def delete_complaint(
    complaint_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    svc.delete_complaint(db, complaint_id)
