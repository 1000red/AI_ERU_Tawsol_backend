from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.content import MaterialFile
from app.schemas.content import MaterialFileCreate, MaterialFileUpdate
from app.services.content_service._helpers import (
    _check_can_manage,
    _require_staff,
)


def get_material_file(db: Session, file_id: int) -> MaterialFile:
    f = db.query(MaterialFile).filter(MaterialFile.file_id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    return f


def get_material_files(db: Session, material_id: str) -> list[MaterialFile]:
    return (
        db.query(MaterialFile)
          .filter(MaterialFile.material_id == material_id)
          .order_by(MaterialFile.created_at.desc())
          .all()
    )


def get_all_files_for_user(
    db: Session,
    user_id: int,
    user_type: str,
    *,
    file_type: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[MaterialFile]:
    """Return all material files across the user's enrolled/taught courses."""
    from app.models.material import MaterialStudent, MaterialTeacher

    if user_type == "STU":
        enrolled = db.query(MaterialStudent.material_id).filter(
            MaterialStudent.user_id == user_id
        ).subquery()
        base = db.query(MaterialFile).filter(MaterialFile.material_id.in_(enrolled))
    else:
        taught = db.query(MaterialTeacher.material_id).filter(
            MaterialTeacher.user_id == user_id
        ).subquery()
        base = db.query(MaterialFile).filter(MaterialFile.material_id.in_(taught))

    if file_type:
        base = base.filter(MaterialFile.file_type == file_type)

    return (
        base.order_by(MaterialFile.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
    )


def create_material_file(
    db: Session,
    data: MaterialFileCreate,
    author_id: int,
    file_path: str | None = None,
) -> MaterialFile:
    _require_staff(db, author_id)  # students cannot upload course files
    material_file = MaterialFile(**data.model_dump(), author_id=author_id, file_path=file_path)
    db.add(material_file)
    db.commit()
    db.refresh(material_file)
    return material_file


def update_material_file(
    db: Session,
    file_id: int,
    data: MaterialFileUpdate,
    user_id: int,
    file_path: str | None = None,
) -> MaterialFile:
    material_file = get_material_file(db, file_id)
    _check_can_manage(db, material_file, user_id)  # author or admin
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(material_file, field, value)
    if file_path:
        material_file.file_path = file_path
    db.commit()
    db.refresh(material_file)
    return material_file


def delete_material_file(db: Session, file_id: int, user_id: int) -> None:
    material_file = get_material_file(db, file_id)
    _check_can_manage(db, material_file, user_id)  # author or admin
    db.delete(material_file)
    db.commit()
