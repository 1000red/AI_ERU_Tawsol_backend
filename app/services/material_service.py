from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.material import Material, MaterialStudent, MaterialTeacher
from app.schemas.material import MaterialCreate, MaterialUpdate


# ── Material CRUD ─────────────────────────────────────────────────────────────

def get_material(db: Session, material_id: str) -> Material:
    m = db.query(Material).filter(Material.material_id == material_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Material not found")
    return m


def get_all_materials(db: Session, skip: int = 0, limit: int = 100) -> list[Material]:
    return db.query(Material).offset(skip).limit(limit).all()


def create_material(db: Session, data: MaterialCreate) -> Material:
    material = Material(**data.model_dump())
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


def update_material(db: Session, material_id: str, data: MaterialUpdate) -> Material:
    material = get_material(db, material_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(material, field, value)
    db.commit()
    db.refresh(material)
    return material


def delete_material(db: Session, material_id: str) -> None:
    material = get_material(db, material_id)
    db.delete(material)
    db.commit()


# ── Student Enrollment ────────────────────────────────────────────────────────

def enroll_student(db: Session, material_id: str, user_id: int) -> MaterialStudent:
    existing = db.query(MaterialStudent).filter_by(
        material_id=material_id, user_id=user_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Student already enrolled")
    enrollment = MaterialStudent(material_id=material_id, user_id=user_id)
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


def unenroll_student(db: Session, material_id: str, user_id: int) -> None:
    enrollment = db.query(MaterialStudent).filter_by(
        material_id=material_id, user_id=user_id
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    db.delete(enrollment)
    db.commit()


def get_student_materials(db: Session, user_id: int) -> list[Material]:
    return (
        db.query(Material)
        .join(MaterialStudent, Material.material_id == MaterialStudent.material_id)
        .filter(MaterialStudent.user_id == user_id)
        .all()
    )


# ── Teacher Assignment ────────────────────────────────────────────────────────

def assign_teacher(db: Session, material_id: str, user_id: int) -> MaterialTeacher:
    existing = db.query(MaterialTeacher).filter_by(
        material_id=material_id, user_id=user_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Teacher already assigned")
    assignment = MaterialTeacher(material_id=material_id, user_id=user_id)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def get_teacher_materials(db: Session, user_id: int) -> list[Material]:
    return (
        db.query(Material)
        .join(MaterialTeacher, Material.material_id == MaterialTeacher.material_id)
        .filter(MaterialTeacher.user_id == user_id)
        .all()
    )
