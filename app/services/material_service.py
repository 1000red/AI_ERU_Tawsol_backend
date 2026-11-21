from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from app.models.material import Material, MaterialStudent, MaterialTeacher
from app.models.user import User
from app.schemas.material import MaterialCreate, MaterialUpdate, EnrollStudentIn, AssignTeacherIn


def get_all_materials(db: Session) -> list[Material]:
    return (
        db.query(Material)
        .options(joinedload(Material.teacher_assignments).joinedload(MaterialTeacher.teacher))
        .order_by(Material.material_id)
        .all()
    )


def get_material_by_id(db: Session, material_id: str) -> Material:
    material = (
        db.query(Material)
        .options(joinedload(Material.teacher_assignments).joinedload(MaterialTeacher.teacher))
        .filter(Material.material_id == material_id)
        .first()
    )
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    return material


def get_student_materials(db: Session, user_id: int) -> list[Material]:
    if user_id <= 0:
        return []
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return []
    if user.type_code == "ADM":
        return get_all_materials(db)

    assigned = (
        db.query(Material)
        .join(MaterialStudent, Material.material_id == MaterialStudent.material_id)
        .filter(MaterialStudent.user_id == user_id)
        .options(joinedload(Material.teacher_assignments).joinedload(MaterialTeacher.teacher))
        .all()
    )
    return assigned


def get_teacher_materials(db: Session, user_id: int) -> list[Material]:
    if user_id <= 0:
        return []
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return []
    if user.type_code == "ADM":
        return get_all_materials(db)

    assigned = (
        db.query(Material)
        .join(MaterialTeacher, Material.material_id == MaterialTeacher.material_id)
        .filter(MaterialTeacher.user_id == user_id)
        .options(joinedload(Material.teacher_assignments).joinedload(MaterialTeacher.teacher))
        .all()
    )
    for m in assigned:
        m.teacher_name = user.name
    return assigned


def create_material(db: Session, data: MaterialCreate) -> Material:
    if not data.material_id or not str(data.material_id).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="material_id cannot be empty"
        )
    existing = db.query(Material).filter(Material.material_id == data.material_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Course with ID '{data.material_id}' already exists"
        )
    
    mat = Material(
        material_id=data.material_id,
        name=data.name,
        description=data.description,
        duration=data.duration or 0,
    )
    db.add(mat)
    db.commit()
    db.refresh(mat)

    if data.teacher_id:
        assignment = MaterialTeacher(
            material_id=mat.material_id,
            user_id=data.teacher_id
        )
        db.add(assignment)
        db.commit()

    return get_material_by_id(db, mat.material_id)


def update_material(db: Session, material_id: str, data: MaterialUpdate) -> Material:
    mat = get_material_by_id(db, material_id)
    if data.name is not None:
        mat.name = data.name
    if data.description is not None:
        mat.description = data.description
    if data.duration is not None:
        mat.duration = data.duration
    
    db.commit()
    db.refresh(mat)
    return get_material_by_id(db, mat.material_id)


def delete_material(db: Session, material_id: str) -> None:
    mat = get_material_by_id(db, material_id)
    db.delete(mat)
    db.commit()


def enroll_student(db: Session, data: EnrollStudentIn) -> MaterialStudent:
    enrollment = MaterialStudent(material_id=data.material_id, user_id=data.user_id)
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


def assign_teacher(db: Session, data: AssignTeacherIn) -> MaterialTeacher:
    assignment = MaterialTeacher(material_id=data.material_id, user_id=data.user_id)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def get_material_students(db: Session, material_id: str) -> list[dict]:
    clean_id = (material_id or "").strip()
    students = []
    if clean_id and clean_id.lower() not in ("all", "none", "default"):
        enrollments = (
            db.query(MaterialStudent)
            .options(joinedload(MaterialStudent.student))
            .filter(MaterialStudent.material_id == clean_id)
            .all()
        )
        for en in enrollments:
            if en.student:
                students.append({
                    "user_id": en.student.user_id,
                    "name": en.student.name,
                    "uni_code": en.student.uni_code or f"WE-{en.student.user_id}",
                    "department": en.student.department or "IT & Networks",
                    "level": en.student.level or 1,
                })
    if not students:
        all_stu = (
            db.query(User)
            .filter(User.type_code == "STU")
            .order_by(User.user_id)
            .limit(40)
            .all()
        )
        for u in all_stu:
            students.append({
                "user_id": u.user_id,
                "name": u.name,
                "uni_code": u.uni_code or f"WE-{u.user_id}",
                "department": u.department or "IT & Networks",
                "level": u.level or 1,
            })
    return students

