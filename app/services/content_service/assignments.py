from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.content import Assignment
from app.schemas.content import AssignmentCreate, AssignmentUpdate
from app.services.content_service._helpers import _check_author


def get_assignment(db: Session, assignment_id: int) -> Assignment:
    a = db.query(Assignment).filter(Assignment.assignment_id == assignment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return a


def get_material_assignments(db: Session, material_id: int) -> list[Assignment]:
    return db.query(Assignment).filter(
        Assignment.material_id == material_id
    ).order_by(Assignment.deadline).all()


def create_assignment(
    db: Session,
    data: AssignmentCreate,
    author_id: int,
    file_path: str | None = None,
) -> Assignment:
    assignment = Assignment(**data.model_dump(), author_id=author_id, file_path=file_path)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def update_assignment(
    db: Session,
    assignment_id: int,
    data: AssignmentUpdate,
    user_id: int,
) -> Assignment:
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
