from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import HTTPException
from datetime import datetime, timedelta
from typing import Optional

from app.models.content import Assignment
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
    from app.models.user import User
    from app.models.material import Material

    author = db.query(User).filter(User.user_id == assignment.author_id).first()

    subject_name = None
    subject_code = None
    if assignment.material_id:
        mat = db.query(Material).filter(Material.material_id == assignment.material_id).first()
        if mat:
            subject_name = mat.name
            subject_code = mat.material_id

    # Files linked via the announcement
    from app.models.content import MaterialFile
    ann_files = []
    if assignment.announcement_id:
        ann_files = (
            db.query(MaterialFile)
              .filter(MaterialFile.announcement_id == assignment.announcement_id)
              .all()
        )

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
        "author_name":      author.name if author else None,
        "subject_name":     subject_name,
        "subject_code":     subject_code,
        "attachments":      ann_files,
    }

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
) -> dict:
    _require_staff(db, author_id)  # students cannot create assignments

    from app.models.content import Announcement

    if data.announcement_id:
        # Link to an existing announcement (e.g. edit-mode type change to assignment).
        linked_ann = db.query(Announcement).filter(
            Announcement.announcement_id == data.announcement_id
        ).first()
        if not linked_ann:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Announcement not found")
        linked_ann.announcement_type = 'assignment'
        db.flush()
    else:
        # Create a linked announcement so the assignment appears in all feeds
        linked_ann = Announcement(
            title=data.title,
            content=data.description or '',
            announcement_type='assignment',
            priority='normal',
            target_type='course',
            target_course_id=data.material_id,
            author_id=author_id,
        )
        db.add(linked_ann)
        db.flush()  # get announcement_id without full commit

    assign_data = data.model_dump(exclude={'announcement_id'})
    assignment = Assignment(
        **assign_data,
        author_id=author_id,
        file_path=file_path,
        announcement_id=linked_ann.announcement_id,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    db.refresh(linked_ann)

    # Mark as read for the author so they don't see the unread dot on their own assignment
    from app.services.content_service.announcements import _mark_as_read
    _mark_as_read(db, linked_ann.announcement_id, author_id)

    viewer = get_user_info(db, author_id)
    return _enrich_assignment(db, assignment, author_id, viewer.type_code)


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
