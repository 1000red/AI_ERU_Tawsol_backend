from sqlalchemy.orm import Session, joinedload

from app.models.material import Material, MaterialStudent, MaterialTeacher


def get_student_materials(db: Session, user_id: int) -> list[Material]:
    return (
        db.query(Material)
        .join(MaterialStudent, Material.material_id == MaterialStudent.material_id)
        .filter(MaterialStudent.user_id == user_id)
        .options(joinedload(Material.teacher_assignments).joinedload(MaterialTeacher.teacher))
        .all()
    )


def get_teacher_materials(db: Session, user_id: int) -> list[Material]:
    return (
        db.query(Material)
        .join(MaterialTeacher, Material.material_id == MaterialTeacher.material_id)
        .filter(MaterialTeacher.user_id == user_id)
        .options(joinedload(Material.teacher_assignments).joinedload(MaterialTeacher.teacher))
        .all()
    )
