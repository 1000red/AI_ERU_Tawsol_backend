from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.material import MaterialOut
from app.services import material_service as svc

router = APIRouter(prefix="/materials", tags=["Materials"])


@router.get("/student/{user_id}", response_model=list[MaterialOut])
def student_materials(user_id: int, db: Session = Depends(get_db)):
    return svc.get_student_materials(db, user_id)


@router.get("/teacher/{user_id}", response_model=list[MaterialOut])
def teacher_materials(user_id: int, db: Session = Depends(get_db)):
    return svc.get_teacher_materials(db, user_id)
