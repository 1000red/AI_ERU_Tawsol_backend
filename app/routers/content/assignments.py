from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.schemas.content import AssignmentCreate, AssignmentUpdate, AssignmentOut
from app.services import content_service as svc
from app.routers.content._helpers import save_file

router = APIRouter(prefix="/assignments", tags=["Assignments"])


@router.get("/{material_id}", response_model=list[AssignmentOut])
def get_assignments(
    material_id: str,
    db: Session = Depends(get_db),
):
    return svc.get_material_assignments(db, material_id)


@router.post("", response_model=AssignmentOut, status_code=201)
def create_assignment(
    material_id: str = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    deadline: str = Form(...),
    link_url: Optional[str] = Form(None),
    file_type: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    file_path = save_file(file)
    data = AssignmentCreate(
        material_id=material_id,
        title=title,
        description=description,
        deadline=datetime.fromisoformat(deadline),
        link_url=link_url,
        file_type=file_type,
    )
    return svc.create_assignment(db, data, user_id, file_path)


@router.put("/{assignment_id}", response_model=AssignmentOut)
def update_assignment(
    assignment_id: int,
    data: AssignmentUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return svc.update_assignment(db, assignment_id, data, user_id)


@router.delete("/{assignment_id}", status_code=204)
def delete_assignment(
    assignment_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    svc.delete_assignment(db, assignment_id, user_id)
