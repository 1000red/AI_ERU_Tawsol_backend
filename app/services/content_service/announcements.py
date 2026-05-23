from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.content import Announcement, AnnouncementRead
from app.schemas.content import AnnouncementCreate, AnnouncementUpdate
from app.services.content_service._helpers import get_user_info, _check_author


def _enrich_announcement(db: Session, ann: Announcement, current_user_id: int) -> dict:
    from app.models.user import User
    from app.models.material import Material

    author = db.query(User).filter(User.user_id == ann.author_id).first()
    author_name = author.name if author else None

    subject_name = None
    if ann.target_course_id:
        material = db.query(Material).filter(Material.material_id == ann.target_course_id).first()
        subject_name = material.name if material else None

    is_read = db.query(AnnouncementRead).filter(
        AnnouncementRead.announcement_id == ann.announcement_id,
        AnnouncementRead.user_id == current_user_id,
    ).first() is not None

    return {
        "announcement_id":   ann.announcement_id,
        "author_id":         ann.author_id,
        "title":             ann.title,
        "content":           ann.content,
        "announcement_type": ann.announcement_type,
        "priority":          ann.priority,
        "target_type":       ann.target_type,
        "target_course_id":  ann.target_course_id,
        "target_department": ann.target_department,
        "target_year":       ann.target_year,
        "target_student_id": ann.target_student_id,
        "created_at":        ann.created_at,
        "updated_at":        ann.updated_at,
        "is_read":           is_read,
        "author_name":       author_name,
        "subject_name":      subject_name,
        "subject_code":      None,
    }


def _mark_as_read(db: Session, announcement_id: int, user_id: int) -> None:
    already = db.query(AnnouncementRead).filter(
        AnnouncementRead.announcement_id == announcement_id,
        AnnouncementRead.user_id == user_id,
    ).first()
    if not already:
        db.add(AnnouncementRead(announcement_id=announcement_id, user_id=user_id))
        db.commit()


def get_announcement(db: Session, announcement_id: int) -> Announcement:
    a = db.query(Announcement).filter(Announcement.announcement_id == announcement_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return a


def get_announcements_for_user(
    db: Session,
    user_id: int,
    user_type: str,
    user_level: int,
    user_department: str | None,
) -> list[dict]:
    from sqlalchemy import or_, and_
    from app.models.material import MaterialStudent

    query = db.query(Announcement)
    conditions = [
        Announcement.target_type == "all",
        and_(Announcement.target_type == "level", Announcement.target_year == user_level),
        and_(Announcement.target_type == "level", Announcement.target_year == user_level, Announcement.target_department == user_department),
        and_(Announcement.target_type == "department", Announcement.target_department == user_department),
        and_(Announcement.target_type == "student", Announcement.target_student_id == user_id),
    ]

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

    announcements = query.filter(or_(*conditions)).order_by(Announcement.created_at.desc()).all()
    return [_enrich_announcement(db, a, user_id) for a in announcements]


def create_announcement(db: Session, data: AnnouncementCreate, author_id: int) -> dict:
    author = get_user_info(db, author_id)
    if author.type_code not in ("ADM", "DR", "TA"):
        raise HTTPException(status_code=403, detail="Only admins, doctors, and teaching assistants can create announcements")
    announcement = Announcement(**data.model_dump(), author_id=author_id)
    db.add(announcement)
    db.commit()
    db.refresh(announcement)
    _mark_as_read(db, announcement.announcement_id, author_id)
    return _enrich_announcement(db, announcement, author_id)


def update_announcement(db: Session, announcement_id: int, data: AnnouncementUpdate, user_id: int) -> dict:
    announcement = get_announcement(db, announcement_id)
    _check_author(announcement, user_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(announcement, field, value)
    db.commit()
    db.refresh(announcement)
    return _enrich_announcement(db, announcement, user_id)


def delete_announcement(db: Session, announcement_id: int, user_id: int) -> None:
    announcement = get_announcement(db, announcement_id)
    _check_author(announcement, user_id)
    db.delete(announcement)
    db.commit()
