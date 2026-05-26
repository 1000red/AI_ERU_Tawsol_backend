from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import HTTPException
from datetime import datetime, timedelta
from typing import Optional

from app.models.content import Assignment, AssignmentSubmission
from app.schemas.content import AssignmentCreate, AssignmentUpdate
from app.services.content_service._helpers import (
    get_user_info,
    _check_can_manage,
    _require_staff,
)


def get_assignment(db: Session, assignment_id: int) -> Assignment:
    a = db.query(Assignment).filter(Assignment.assignment_id == assignment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return a


def _enrich_assignment(db: Session, assignment: Assignment, viewer_id: int, viewer_type: str) -> dict:
    data = {
        "assignment_id":    assignment.assignment_id,
        "material_id":      assignment.material_id,
        "author_id":        assignment.author_id,
        "announcement_id":  assignment.announcement_id,
        "title":            assignment.title,
        "description":      assignment.description,
        "deadline":         assignment.deadline,
        "file_type":        assignment.file_type,
        "file_path":        assignment.file_path,
        "link_url":         assignment.link_url,
        "text_content":     assignment.text_content,
        "created_at":       assignment.created_at,
        "updated_at":       assignment.updated_at,
        "has_submitted":    None,
        "my_submission_id": None,
        "submission_count": None,
    }

    if viewer_type == "STU":
        sub = db.query(AssignmentSubmission).filter(
            AssignmentSubmission.assignment_id == assignment.assignment_id,
            AssignmentSubmission.student_id == viewer_id,
        ).first()
        data["has_submitted"]    = sub is not None
        data["my_submission_id"] = sub.submission_id if sub else None
    elif viewer_type in ("DR", "TA", "ADM"):
        data["submission_count"] = db.query(AssignmentSubmission).filter(
            AssignmentSubmission.assignment_id == assignment.assignment_id
        ).count()

    return data


def get_assignment_detail(db: Session, assignment_id: int, viewer_id: int) -> dict:
    assignment = get_assignment(db, assignment_id)
    viewer = get_user_info(db, viewer_id)
    return _enrich_assignment(db, assignment, viewer_id, viewer.type_code)


def get_material_assignments(
    db: Session,
    material_id: str,
    viewer_id: Optional[int] = None,
    viewer_type: Optional[str] = None,
) -> list[dict]:
    assignments = (
        db.query(Assignment)
          .filter(Assignment.material_id == material_id)
          .order_by(Assignment.deadline)
          .all()
    )
    if viewer_id and viewer_type:
        return [_enrich_assignment(db, a, viewer_id, viewer_type) for a in assignments]
    return assignments  # type: ignore[return-value]


def get_all_assignments_for_user(
    db: Session,
    user_id: int,
    user_type: str,
    *,
    status: Optional[str] = None,  # "upcoming" | "overdue" | "all" (default)
    skip: int = 0,
    limit: int = 50,
) -> list[dict]:
    """Return all assignments across the user's enrolled/taught courses."""
    from app.models.material import MaterialStudent, MaterialTeacher

    now = datetime.utcnow()

    if user_type == "STU":
        enrolled = db.query(MaterialStudent.material_id).filter(
            MaterialStudent.user_id == user_id
        ).subquery()
        base = db.query(Assignment).filter(Assignment.material_id.in_(enrolled))
    else:
        taught = db.query(MaterialTeacher.material_id).filter(
            MaterialTeacher.user_id == user_id
        ).subquery()
        base = db.query(Assignment).filter(Assignment.material_id.in_(taught))

    if status == "upcoming":
        base = base.filter(Assignment.deadline >= now)
    elif status == "overdue":
        base = base.filter(Assignment.deadline < now)

    assignments = (
        base.order_by(Assignment.deadline)
            .offset(skip)
            .limit(limit)
            .all()
    )
    return [_enrich_assignment(db, a, user_id, user_type) for a in assignments]


def get_upcoming_deadlines(
    db: Session,
    user_id: int,
    user_type: str,
    *,
    days: int = 7,
) -> list[dict]:
    from app.models.material import MaterialStudent, MaterialTeacher

    now = datetime.utcnow()
    cutoff = now + timedelta(days=days)

    if user_type == "STU":
        enrolled = db.query(MaterialStudent.material_id).filter(
            MaterialStudent.user_id == user_id
        ).subquery()
        assignments = (
            db.query(Assignment)
              .filter(
                  Assignment.material_id.in_(enrolled),
                  Assignment.deadline >= now,
                  Assignment.deadline <= cutoff,
              )
              .order_by(Assignment.deadline)
              .all()
        )
    else:
        taught = db.query(MaterialTeacher.material_id).filter(
            MaterialTeacher.user_id == user_id
        ).subquery()
        assignments = (
            db.query(Assignment)
              .filter(
                  Assignment.material_id.in_(taught),
                  Assignment.deadline >= now,
                  Assignment.deadline <= cutoff,
              )
              .order_by(Assignment.deadline)
              .all()
        )

    return [_enrich_assignment(db, a, user_id, user_type) for a in assignments]


def create_assignment(
    db: Session,
    data: AssignmentCreate,
    author_id: int,
    file_path: Optional[str] = None,
) -> Assignment:
    _require_staff(db, author_id)  # students cannot create assignments
    assignment = Assignment(**data.model_dump(), author_id=author_id, file_path=file_path)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    from app.models.material import Material
    from app.services.notification_service import notify_assignment
    mat = db.query(Material).filter(Material.material_id == assignment.material_id).first()
    notify_assignment(db, assignment, course_name=mat.name if mat else None)

    return assignment


def update_assignment(
    db: Session,
    assignment_id: int,
    data: AssignmentUpdate,
    user_id: int,
) -> Assignment:
    assignment = get_assignment(db, assignment_id)
    _check_can_manage(db, assignment, user_id)  # author or admin
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(assignment, field, value)
    db.commit()
    db.refresh(assignment)
    return assignment


def delete_assignment(db: Session, assignment_id: int, user_id: int) -> None:
    assignment = get_assignment(db, assignment_id)
    _check_can_manage(db, assignment, user_id)  # author or admin
    db.delete(assignment)
    db.commit()
