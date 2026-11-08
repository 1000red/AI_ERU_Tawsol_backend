from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.material import (
    MaterialOut,
    MaterialCreate,
    MaterialUpdate,
    EnrollStudentIn,
    AssignTeacherIn,
    EnrollmentOut,
)
from app.services import material_service as svc

router = APIRouter(tags=["Materials"])


@router.get("", response_model=list[MaterialOut])
@router.get("/", response_model=list[MaterialOut])
def list_materials(db: Session = Depends(get_db)):
    """Return all available courses / materials."""
    return svc.get_all_materials(db)


@router.post("", response_model=MaterialOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=MaterialOut, status_code=status.HTTP_201_CREATED)
def create_material(data: MaterialCreate, db: Session = Depends(get_db)):
    """Add a new course / material."""
    return svc.create_material(db, data)


@router.get("/student/{user_id}", response_model=list[MaterialOut])
def student_materials(user_id: int, db: Session = Depends(get_db)):
    """Return courses for a student (or all courses if user is admin)."""
    return svc.get_student_materials(db, user_id)


@router.get("/teacher/{user_id}", response_model=list[MaterialOut])
def teacher_materials(user_id: int, db: Session = Depends(get_db)):
    """Return courses taught by a doctor/teacher (or all courses if user is admin)."""
    return svc.get_teacher_materials(db, user_id)


@router.get("/{material_id}", response_model=MaterialOut)
def get_material(material_id: str, db: Session = Depends(get_db)):
    """Get single course details."""
    return svc.get_material_by_id(db, material_id)


@router.put("/{material_id}", response_model=MaterialOut)
def update_material(material_id: str, data: MaterialUpdate, db: Session = Depends(get_db)):
    """Update a course."""
    return svc.update_material(db, material_id, data)


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(material_id: str, db: Session = Depends(get_db)):
    """Delete a course."""
    svc.delete_material(db, material_id)
    return None


@router.post("/enroll", response_model=EnrollmentOut)
def enroll_student(data: EnrollStudentIn, db: Session = Depends(get_db)):
    """Enroll a student in a course."""
    return svc.enroll_student(db, data)


@router.post("/assign-teacher", response_model=EnrollmentOut)
def assign_teacher(data: AssignTeacherIn, db: Session = Depends(get_db)):
    """Assign a doctor/teacher to a course."""
    return svc.assign_teacher(db, data)
