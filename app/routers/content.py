from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
import shutil, os, uuid
from datetime import datetime

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.schemas.content import (
    AnnouncementCreate, AnnouncementUpdate, AnnouncementOut,
    MaterialFileCreate, MaterialFileUpdate, MaterialFileOut,
    AssignmentCreate, AssignmentUpdate, AssignmentOut,
    SubmissionCreate, SubmissionUpdate, SubmissionOut,
)
from app.services import content_service as svc

router = APIRouter(prefix="/content", tags=["Content"])

UPLOAD_DIR = "uploads/content"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────

def save_file(file: UploadFile) -> str:
    if not file:
        return None
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)

    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return path


# ─────────────────────────────────────────────────────────────
# Announcements
# ─────────────────────────────────────────────────────────────

@router.get("/announcements", response_model=list[AnnouncementOut])
def get_announcements(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = svc.get_user_info(db, user_id)
    return svc.get_announcements_for_user(
        db,
        user_id=user_id,
        user_type=user.type_code,
        user_level=user.level,
        user_department=user.department,
    )


@router.post("/announcements", response_model=AnnouncementOut, status_code=201)
def create_announcement(
    data: AnnouncementCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return svc.create_announcement(db, data, user_id)


@router.put("/announcements/{announcement_id}", response_model=AnnouncementOut)
def update_announcement(
    announcement_id: int,
    data: AnnouncementUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return svc.update_announcement(db, announcement_id, data, user_id)


@router.delete("/announcements/{announcement_id}", status_code=204)
def delete_announcement(
    announcement_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    svc.delete_announcement(db, announcement_id, user_id)


# ─────────────────────────────────────────────────────────────
# Material Files
# ─────────────────────────────────────────────────────────────

@router.get("/files/{material_id}", response_model=list[MaterialFileOut])
def get_files(
    material_id: int,
    db: Session = Depends(get_db),
):
    return svc.get_material_files(db, material_id)


@router.post("/files", response_model=MaterialFileOut, status_code=201)
def create_file(
    material_id: int = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    file_type: str = Form(...),
    link_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    file_path = save_file(file)

    data = MaterialFileCreate(
        material_id=material_id,
        title=title,
        description=description,
        file_type=file_type,
        link_url=link_url,
    )

    return svc.create_material_file(db, data, user_id, file_path)


@router.put("/files/{file_id}", response_model=MaterialFileOut)
def update_file(
    file_id: int,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    link_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    file_path = save_file(file)

    data = MaterialFileUpdate(
        title=title,
        description=description,
        link_url=link_url,
    )

    return svc.update_material_file(db, file_id, data, user_id, file_path)


@router.delete("/files/{file_id}", status_code=204)
def delete_file(
    file_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    svc.delete_material_file(db, file_id, user_id)


# ─────────────────────────────────────────────────────────────
# Assignments
# ─────────────────────────────────────────────────────────────

@router.get("/assignments/{material_id}", response_model=list[AssignmentOut])
def get_assignments(
    material_id: int,
    db: Session = Depends(get_db),
):
    return svc.get_material_assignments(db, material_id)


@router.post("/assignments", response_model=AssignmentOut, status_code=201)
def create_assignment(
    material_id: int = Form(...),
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


@router.put("/assignments/{assignment_id}", response_model=AssignmentOut)
def update_assignment(
    assignment_id: int,
    data: AssignmentUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return svc.update_assignment(db, assignment_id, data, user_id)


@router.delete("/assignments/{assignment_id}", status_code=204)
def delete_assignment(
    assignment_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    svc.delete_assignment(db, assignment_id, user_id)


# ─────────────────────────────────────────────────────────────
# Submissions
# ─────────────────────────────────────────────────────────────

@router.get("/submissions/{assignment_id}", response_model=list[SubmissionOut])
def get_submissions(
    assignment_id: int,
    db: Session = Depends(get_db),
):
    return svc.get_assignment_submissions(db, assignment_id)


@router.post("/submissions", response_model=SubmissionOut, status_code=201)
def create_submission(
    assignment_id: int = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    link_url: Optional[str] = Form(None),
    file_type: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    file_path = save_file(file)

    data = SubmissionCreate(
        assignment_id=assignment_id,
        title=title,
        description=description,
        link_url=link_url,
        file_type=file_type,
    )

    return svc.create_submission(db, data, user_id, file_path)


@router.put("/submissions/{submission_id}", response_model=SubmissionOut)
def update_submission(
    submission_id: int,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    link_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    file_path = save_file(file)

    data = SubmissionUpdate(
        title=title,
        description=description,
        link_url=link_url,
    )

    return svc.update_submission(db, submission_id, data, user_id, file_path)


@router.delete("/submissions/{submission_id}", status_code=204)
def delete_submission(
    submission_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    svc.delete_submission(db, submission_id, user_id)