from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime

from app.models.content import Announcement, MaterialFile, Assignment, AssignmentSubmission
from app.schemas.content import (
    AnnouncementCreate, AnnouncementUpdate,
    MaterialFileCreate, MaterialFileUpdate,
    AssignmentCreate, AssignmentUpdate,
    SubmissionCreate, SubmissionUpdate,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_user_info(db: Session, user_id: int):
    from app.models.user import User
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _check_author(obj, user_id: int):
    if obj.author_id != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")


# ── Announcement ──────────────────────────────────────────────────────────────

def get_announcement(db: Session, announcement_id: int) -> Announcement:
    a = db.query(Announcement).filter(Announcement.announcement_id == announcement_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return a


def get_announcements_for_user(db: Session, user_id: int, user_type: str, user_level: int, user_department: str | None) -> list[Announcement]:
    """جيب كل الإعلانات اللي تخص اليوزر ده حسب الـ target"""
    from sqlalchemy import or_, and_
    from app.models.material import MaterialStudent

    query = db.query(Announcement)

    # الإعلانات المتاحة لليوزر ده
    conditions = [
        Announcement.target_type == "all",
        and_(Announcement.target_type == "level", Announcement.target_year == user_level),
        and_(Announcement.target_type == "level", Announcement.target_year == user_level, Announcement.target_department == user_department),
        and_(Announcement.target_type == "department", Announcement.target_department == user_department),
        and_(Announcement.target_type == "student", Announcement.target_student_id == user_id),
    ]

    # لو طالب، ضيف الـ course announcements بتاعته
    if user_type == "STU":
        enrolled_courses = db.query(MaterialStudent.material_id).filter(MaterialStudent.user_id == user_id).subquery()
        conditions.append(
            and_(
                Announcement.target_type == "course",
                Announcement.target_course_id.in_(enrolled_courses),
            )
        )
        conditions.append(
            and_(
                Announcement.target_type == "course_department",
                Announcement.target_course_id.in_(enrolled_courses),
                Announcement.target_department == user_department,
            )
        )

    return query.filter(or_(*conditions)).order_by(Announcement.created_at.desc()).all()


def create_announcement(db: Session, data: AnnouncementCreate, author_id: int) -> Announcement:
    announcement = Announcement(**data.model_dump(), author_id=author_id)
    db.add(announcement)
    db.commit()
    db.refresh(announcement)
    return announcement


def update_announcement(db: Session, announcement_id: int, data: AnnouncementUpdate, user_id: int) -> Announcement:
    announcement = get_announcement(db, announcement_id)
    _check_author(announcement, user_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(announcement, field, value)
    db.commit()
    db.refresh(announcement)
    return announcement


def delete_announcement(db: Session, announcement_id: int, user_id: int) -> None:
    announcement = get_announcement(db, announcement_id)
    _check_author(announcement, user_id)
    db.delete(announcement)
    db.commit()


# ── MaterialFile ──────────────────────────────────────────────────────────────

def get_material_file(db: Session, file_id: int) -> MaterialFile:
    f = db.query(MaterialFile).filter(MaterialFile.file_id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    return f


def get_material_files(db: Session, material_id: int) -> list[MaterialFile]:
    return db.query(MaterialFile).filter(
        MaterialFile.material_id == material_id
    ).order_by(MaterialFile.created_at.desc()).all()


def create_material_file(db: Session, data: MaterialFileCreate, author_id: int, file_path: str | None = None) -> MaterialFile:
    material_file = MaterialFile(**data.model_dump(), author_id=author_id, file_path=file_path)
    db.add(material_file)
    db.commit()
    db.refresh(material_file)
    return material_file


def update_material_file(db: Session, file_id: int, data: MaterialFileUpdate, user_id: int, file_path: str | None = None) -> MaterialFile:
    material_file = get_material_file(db, file_id)
    _check_author(material_file, user_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(material_file, field, value)
    if file_path:
        material_file.file_path = file_path
    db.commit()
    db.refresh(material_file)
    return material_file


def delete_material_file(db: Session, file_id: int, user_id: int) -> None:
    material_file = get_material_file(db, file_id)
    _check_author(material_file, user_id)
    db.delete(material_file)
    db.commit()


# ── Assignment ────────────────────────────────────────────────────────────────

def get_assignment(db: Session, assignment_id: int) -> Assignment:
    a = db.query(Assignment).filter(Assignment.assignment_id == assignment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return a


def get_material_assignments(db: Session, material_id: int) -> list[Assignment]:
    return db.query(Assignment).filter(
        Assignment.material_id == material_id
    ).order_by(Assignment.deadline).all()


def create_assignment(db: Session, data: AssignmentCreate, author_id: int, file_path: str | None = None) -> Assignment:
    assignment = Assignment(**data.model_dump(), author_id=author_id, file_path=file_path)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def update_assignment(db: Session, assignment_id: int, data: AssignmentUpdate, user_id: int) -> Assignment:
    assignment = get_assignment(db, assignment_id)
    _check_author(assignment, user_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(assignment, field, value)
    db.commit()
    db.refresh(assignment)
    return assignment


def delete_assignment(db: Session, assignment_id: int, user_id: int) -> None:
    assignment = get_assignment(db, assignment_id)
    _check_author(assignment, user_id)
    db.delete(assignment)
    db.commit()


# ── AssignmentSubmission ──────────────────────────────────────────────────────

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


def create_submission(db: Session, data: SubmissionCreate, student_id: int, file_path: str | None = None) -> AssignmentSubmission:
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


def update_submission(db: Session, submission_id: int, data: SubmissionUpdate, student_id: int, file_path: str | None = None) -> AssignmentSubmission:
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