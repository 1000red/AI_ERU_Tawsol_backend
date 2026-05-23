from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime

from app.models.content import AssignmentSubmission
from app.schemas.content import SubmissionCreate, SubmissionUpdate
from app.services.content_service.assignments import get_assignment


def get_submission(db: Session, submission_id: int) -> AssignmentSubmission:
    s = db.query(AssignmentSubmission).filter(AssignmentSubmission.submission_id == submission_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Submission not found")
    return s


def get_assignment_submissions(db: Session, assignment_id: int) -> list[AssignmentSubmission]:
    return db.query(AssignmentSubmission).filter(
        AssignmentSubmission.assignment_id == assignment_id
    ).all()


def get_student_submission(db: Session, assignment_id: int, student_id: int) -> AssignmentSubmission | None:
    return db.query(AssignmentSubmission).filter(
        AssignmentSubmission.assignment_id == assignment_id,
        AssignmentSubmission.student_id == student_id,
    ).first()


def create_submission(
    db: Session,
    data: SubmissionCreate,
    student_id: int,
    file_path: str | None = None,
) -> AssignmentSubmission:
    assignment = get_assignment(db, data.assignment_id)
    if datetime.utcnow() > assignment.deadline:
        raise HTTPException(status_code=400, detail="Deadline has passed")
    if get_student_submission(db, data.assignment_id, student_id):
        raise HTTPException(status_code=400, detail="Already submitted, update your submission instead")
    submission = AssignmentSubmission(**data.model_dump(), student_id=student_id, file_path=file_path)
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


def update_submission(
    db: Session,
    submission_id: int,
    data: SubmissionUpdate,
    student_id: int,
    file_path: str | None = None,
) -> AssignmentSubmission:
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
    return submission


def delete_submission(db: Session, submission_id: int, student_id: int) -> None:
    submission = get_submission(db, submission_id)
    if submission.student_id != student_id:
        raise HTTPException(status_code=403, detail="Not allowed")
    assignment = get_assignment(db, submission.assignment_id)
    if datetime.utcnow() > assignment.deadline:
        raise HTTPException(status_code=400, detail="Deadline has passed, cannot delete submission")
    db.delete(submission)
    db.commit()
