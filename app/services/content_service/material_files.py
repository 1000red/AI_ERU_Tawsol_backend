from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.content import MaterialFile
from app.schemas.content import MaterialFileCreate, MaterialFileUpdate
from app.services.content_service._helpers import _check_author


def get_material_file(db: Session, file_id: int) -> MaterialFile:
    f = db.query(MaterialFile).filter(MaterialFile.file_id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    return f


def get_material_files(db: Session, material_id: int) -> list[MaterialFile]:
    return db.query(MaterialFile).filter(
        MaterialFile.material_id == material_id
    ).order_by(MaterialFile.created_at.desc()).all()


def create_material_file(
    db: Session,
    data: MaterialFileCreate,
    author_id: int,
    file_path: str | None = None,
) -> MaterialFile:
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
