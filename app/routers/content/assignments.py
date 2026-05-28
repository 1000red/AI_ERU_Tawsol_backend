from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.schemas.content import AssignmentCreate, AssignmentUpdate, AssignmentOut
from app.services import content_service as svc
from app.routers.content._helpers import save_file

router = APIRouter(prefix="/assignments", tags=["Assignments"])


@router.get("", response_model=list[AssignmentOut])
def get_all_assignments(
    status: Optional[str] = Query(None, description="upcoming | overdue | all"),
    skip:   int           = Query(0, ge=0),
    limit:  int           = Query(50, ge=1, le=200),
    user_id: int = Depends(get_current_user_id),
    db: Session  = Depends(get_db),
):
    """Return all assignments for the current user across their enrolled / taught courses."""
    user = svc.get_user_info(db, user_id)
    return svc.get_all_assignments_for_user(
        db, user_id, user.type_code,
        status=status, skip=skip, limit=limit,
    )


@router.get("/upcoming", response_model=list[AssignmentOut])
def get_upcoming_deadlines(
    days:    int = Query(7, ge=1, le=90, description="Look-ahead window in days"),
    user_id: int = Depends(get_current_user_id),
    db: Session  = Depends(get_db),
):
    """Assignments with deadlines within the next N days."""
    user = svc.get_user_info(db, user_id)
    return svc.get_upcoming_deadlines(db, user_id, user.type_code, days=days)


@router.get("/detail/{assignment_id}", response_model=AssignmentOut)
def get_assignment_detail(
    assignment_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session  = Depends(get_db),
):
    """Fetch a single assignment with viewer-enriched fields."""
    return svc.get_assignment_detail(db, assignment_id, user_id)


@router.get("/{material_id}", response_model=list[AssignmentOut])
def get_assignments(
    material_id: str,
    user_id: int = Depends(get_current_user_id),
    db: Session  = Depends(get_db),
):
    user = svc.get_user_info(db, user_id)
    return svc.get_material_assignments(
        db, material_id, viewer_id=user_id, viewer_type=user.type_code
    )


@router.post("", response_model=AssignmentOut, status_code=201)
def create_assignment(
    material_id:     str            = Form(...),
    title:           str            = Form(...),
    description:     Optional[str]  = Form(None),
    deadline:        str            = Form(...),
    link_url:        Optional[str]  = Form(None),
    file_type:       Optional[str]  = Form(None),
    text_content:    Optional[str]  = Form(None),
    announcement_id: Optional[int]  = Form(None),
    file:            Optional[UploadFile] = File(None),
    user_id: int  = Depends(get_current_user_id),
    db: Session   = Depends(get_db),
):
    file_path, _ = save_file(file)
    data = AssignmentCreate(
        material_id=material_id,
        title=title,
        description=description,
        deadline=datetime.fromisoformat(deadline),
        link_url=link_url,
        file_type=file_type,
        text_content=text_content,
        announcement_id=announcement_id,
    )
    return svc.create_assignment(db, data, user_id, file_path)


@router.put("/{assignment_id}", response_model=AssignmentOut)
def update_assignment(
    assignment_id: int,
    data: AssignmentUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session  = Depends(get_db),
):
    return svc.update_assignment(db, assignment_id, data, user_id)


@router.delete("/{assignment_id}", status_code=204)
def delete_assignment(
    assignment_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session  = Depends(get_db),
):
    svc.delete_assignment(db, assignment_id, user_id)
