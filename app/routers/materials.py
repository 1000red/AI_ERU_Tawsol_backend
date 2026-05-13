from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.schemas.material import MaterialCreate, MaterialUpdate, MaterialOut, EnrollmentOut, EnrollStudentIn, AssignTeacherIn
from app.services import material_service as svc

router = APIRouter(prefix="/materials", tags=["Materials"])


# ── Material CRUD ─────────────────────────────────────────────────────────────

@router.get("/", response_model=list[MaterialOut])
def list_materials(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return svc.get_all_materials(db, skip, limit)


@router.post("/", response_model=MaterialOut, status_code=201)
def create_material(data: MaterialCreate, db: Session = Depends(get_db)):
    return svc.create_material(db, data)


@router.get("/{material_id}", response_model=MaterialOut)
def get_material(material_id: int, db: Session = Depends(get_db)):
    return svc.get_material(db, material_id)


@router.put("/{material_id}", response_model=MaterialOut)
def update_material(material_id: int, data: MaterialUpdate, db: Session = Depends(get_db)):
    return svc.update_material(db, material_id, data)


@router.delete("/{material_id}", status_code=204)
def delete_material(material_id: int, db: Session = Depends(get_db)):
    svc.delete_material(db, material_id)


# ── Student Enrollment ────────────────────────────────────────────────────────

@router.post("/enroll/student", response_model=EnrollmentOut, status_code=201)
def enroll_student(data: EnrollStudentIn, db: Session = Depends(get_db)):
    return svc.enroll_student(db, data.material_id, data.user_id)


@router.delete("/enroll/student/{material_id}/{user_id}", status_code=204)
def unenroll_student(material_id: int, user_id: int, db: Session = Depends(get_db)):
    svc.unenroll_student(db, material_id, user_id)


@router.get("/student/{user_id}", response_model=list[MaterialOut])
def student_materials(user_id: int, db: Session = Depends(get_db)):
    return svc.get_student_materials(db, user_id)


# ── Teacher Assignment ────────────────────────────────────────────────────────

@router.post("/assign/teacher", response_model=EnrollmentOut, status_code=201)
def assign_teacher(data: AssignTeacherIn, db: Session = Depends(get_db)):
    return svc.assign_teacher(db, data.material_id, data.user_id)


@router.get("/teacher/{user_id}", response_model=list[MaterialOut])
def teacher_materials(user_id: int, db: Session = Depends(get_db)):
    return svc.get_teacher_materials(db, user_id)
