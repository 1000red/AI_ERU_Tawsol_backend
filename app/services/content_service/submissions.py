from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime
from typing import Optional

from app.models.content import AssignmentSubmission
from app.schemas.content import SubmissionCreate, SubmissionUpdate
from app.services.content_service.assignments import get_assignment
from app.services.content_service._helpers import get_user_info


def _enrich_submission(db: Session, sub: AssignmentSubmission) -> dict:
    from app.models.user import User
    student = db.query(User).filter(User.user_id == sub.student_id).first()
    return {
        "submission_id": sub.submission_id,
        "assignment_id": sub.assignment_id,
        "student_id":    sub.student_id,
        "title":         sub.title,
        "description":   sub.description,
        "file_type":     sub.file_type,
        "file_path":     sub.file_path,
        "link_url":      sub.link_url,
        "text_content":  sub.text_content,
        "submitted_at":  sub.submitted_at,
        "updated_at":    sub.updated_at,
        "student_name":  student.name if student else None,
    }


def get_submission(db: Session, submission_id: int) -> AssignmentSubmission:
    s = db.query(AssignmentSubmission).filter(AssignmentSubmission.submission_id == submission_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Submission not found")
    return s


def get_assignment_submissions(db: Session, assignment_id: int) -> list[dict]:
    subs = db.query(AssignmentSubmission).filter(
        AssignmentSubmission.assignment_id == assignment_id
    ).all()
    return [_enrich_submission(db, s) for s in subs]


def get_student_submission(db: Session, assignment_id: int, student_id: int) -> Optional[AssignmentSubmission]:
    return db.query(AssignmentSubmission).filter(
        AssignmentSubmission.assignment_id == assignment_id,
        AssignmentSubmission.student_id == student_id,
    ).first()


def get_my_submission(db: Session, assignment_id: int, student_id: int) -> dict:
    sub = get_student_submission(db, assignment_id, student_id)
    if not sub:
        raise HTTPException(status_code=404, detail="No submission found")
    return _enrich_submission(db, sub)


def create_submission(
    db: Session,
    data: SubmissionCreate,
    student_id: int,
    file_path: Optional[str] = None,
) -> dict:
    assignment = get_assignment(db, data.assignment_id)
    if datetime.utcnow() > assignment.deadline:
        raise HTTPException(status_code=400, detail="Deadline has passed")
    if get_student_submission(db, data.assignment_id, student_id):
        raise HTTPException(status_code=400, detail="Already submitted; update your submission instead")
    submission = AssignmentSubmission(**data.model_dump(), student_id=student_id, file_path=file_path)
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return _enrich_submission(db, submission)


def update_submission(
    db: Session,
    submission_id: int,
    data: SubmissionUpdate,
    student_id: int,
    file_path: Optional[str] = None,
) -> dict:
    submission = get_submission(db, submission_id)
    if submission.student_id != student_id:
        raise HTTPException(status_code=403, detail="Not allowed")
    assignment = get_assignment(db, submission.assignment_id)
    if datetime.utcnow() > assignment.deadline:
        raise HTTPException(status_code=400, detail="Deadline has passed")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(submission, field, value)
    if file_path:
        submission.file_path = file_path
    db.commit()
    db.refresh(submission)
    return _enrich_submission(db, submission)


def delete_submission(db: Session, submission_id: int, student_id: int) -> None:
    submission = get_submission(db, submission_id)
    if submission.student_id != student_id:
        raise HTTPException(status_code=403, detail="Not allowed")
    assignment = get_assignment(db, submission.assignment_id)
    if datetime.utcnow() > assignment.deadline:
        raise HTTPException(status_code=400, detail="Deadline has passed, cannot delete submission")
    db.delete(submission)
    db.commit()
