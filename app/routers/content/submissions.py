from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.schemas.content import SubmissionCreate, SubmissionUpdate, SubmissionOut
from app.services import content_service as svc
from app.routers.content._helpers import save_file

router = APIRouter(prefix="/submissions", tags=["Submissions"])


@router.get("/{assignment_id}", response_model=list[SubmissionOut])
def get_submissions(
    assignment_id: int,
    db: Session = Depends(get_db),
):
    return svc.get_assignment_submissions(db, assignment_id)


@router.get("/my/{assignment_id}", response_model=SubmissionOut)
def get_my_submission(
    assignment_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session  = Depends(get_db),
):
    return svc.get_my_submission(db, assignment_id, user_id)


@router.post("", response_model=SubmissionOut, status_code=201)
def create_submission(
    assignment_id: int            = Form(...),
    title:         Optional[str]  = Form(None),
    description:   Optional[str]  = Form(None),
    link_url:      Optional[str]  = Form(None),
    file_type:     Optional[str]  = Form(None),
    file:          Optional[UploadFile] = File(None),
    user_id: int   = Depends(get_current_user_id),
    db: Session    = Depends(get_db),
):
    file_path, _ = save_file(file)
    data = SubmissionCreate(
        assignment_id=assignment_id,
        title=title,
        description=description,
        link_url=link_url,
        file_type=file_type,
    )
    return svc.create_submission(db, data, user_id, file_path)


@router.put("/{submission_id}", response_model=SubmissionOut)
def update_submission(
    submission_id: int,
    title:         Optional[str]  = Form(None),
    description:   Optional[str]  = Form(None),
    link_url:      Optional[str]  = Form(None),
    file:          Optional[UploadFile] = File(None),
    user_id: int   = Depends(get_current_user_id),
    db: Session    = Depends(get_db),
):
    file_path, _ = save_file(file)
    fields = {k: v for k, v in {
        "title": title, "description": description, "link_url": link_url,
    }.items() if v is not None}
    data = SubmissionUpdate(**fields)
    return svc.update_submission(db, submission_id, data, user_id, file_path)


@router.delete("/{submission_id}", status_code=204)
def delete_submission(
    submission_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session  = Depends(get_db),
):
    svc.delete_submission(db, submission_id, user_id)
