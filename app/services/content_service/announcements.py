from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from fastapi import HTTPException
from typing import Optional

from app.models.content import Announcement, AnnouncementRead, MaterialFile
from app.models.content.announcement import AnnouncementTargetUser
from app.schemas.content import AnnouncementCreate, AnnouncementUpdate
from app.services.content_service._helpers import get_user_info, _check_can_manage


# ── Internal helpers ──────────────────────────────────────────────────────────

def _enrich_announcement(db: Session, ann: Announcement, current_user_id: int) -> dict:
    from app.models.user import User
    from app.models.material import Material

    author = db.query(User).filter(User.user_id == ann.author_id).first()

    subject_name = None
    subject_code = None
    if ann.target_course_id:
        mat = db.query(Material).filter(Material.material_id == ann.target_course_id).first()
        if mat:
            subject_name = mat.name
            subject_code = mat.material_id

    is_read = db.query(AnnouncementRead).filter(
        AnnouncementRead.announcement_id == ann.announcement_id,
        AnnouncementRead.user_id == current_user_id,
    ).first() is not None

    target_user_ids = [
        tu.user_id for tu in
        db.query(AnnouncementTargetUser)
          .filter(AnnouncementTargetUser.announcement_id == ann.announcement_id)
          .all()
    ]

    files = (
        db.query(MaterialFile)
          .filter(MaterialFile.announcement_id == ann.announcement_id)
          .all()
    )

    deadline = None
    assignment_id = None
    if ann.announcement_type == 'assignment' and ann.assignment:
        deadline = ann.assignment.deadline
        assignment_id = ann.assignment.assignment_id
    
    is_from_admin = (author.type_code == "ADM") if author else False

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
        "target_user_ids":   target_user_ids,
        "target_role":       ann.target_role,
        "created_at":        ann.created_at,
        "updated_at":        ann.updated_at,
        "is_read":           is_read,
        "author_name":       author.name if author else None,
        "subject_name":      subject_name,
        "subject_code":      subject_code,
        "attachments":       files,
        "is_from_admin":     is_from_admin,
        "deadline":          deadline,
        "assignment_id":     assignment_id,
    }


def _mark_as_read(db: Session, announcement_id: int, user_id: int) -> None:
    already = db.query(AnnouncementRead).filter(
        AnnouncementRead.announcement_id == announcement_id,
        AnnouncementRead.user_id == user_id,
    ).first()
    if not already:
        db.add(AnnouncementRead(announcement_id=announcement_id, user_id=user_id))
        db.commit()


# ── Public CRUD ───────────────────────────────────────────────────────────────

def get_announcement(db: Session, announcement_id: int) -> Announcement:
    a = db.query(Announcement).filter(Announcement.announcement_id == announcement_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return a


def get_announcement_detail(db: Session, announcement_id: int, current_user_id: int) -> dict:
    """Return single enriched announcement and mark it as read."""
    ann = get_announcement(db, announcement_id)
    _mark_as_read(db, announcement_id, current_user_id)
    return _enrich_announcement(db, ann, current_user_id)


def get_announcements_for_user(
    db: Session,
    user_id: int,
    user_type: str,
    user_level: int,
    user_department: Optional[str],
    *,
    announcement_type: Optional[str] = None,
    priority: Optional[str] = None,
    target_course_id: Optional[str] = None,
    unread_only: bool = False,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[dict]:
    from app.models.material import MaterialStudent

    # Build conditions — "users" target type is handled separately via subquery
    conditions = [
        Announcement.target_type == "all",
        and_(Announcement.target_type == "level", Announcement.target_year == user_level),
        and_(
            Announcement.target_type == "level",
            Announcement.target_year == user_level,
            Announcement.target_department == user_department,
        ),
        and_(Announcement.target_type == "department", Announcement.target_department == user_department),
        and_(Announcement.target_type == "student", Announcement.target_student_id == user_id),
        # role-based targeting: target_type="role" with matching target_role
        and_(Announcement.target_type == "role", Announcement.target_role == user_type),
    ]

    if user_type == "STU":
        enrolled = db.query(MaterialStudent.material_id).filter(MaterialStudent.user_id == user_id).scalar_subquery()
        conditions.append(and_(Announcement.target_type == "course",
                               Announcement.target_course_id.in_(enrolled)))
        conditions.append(and_(Announcement.target_type == "course_department",
                               Announcement.target_course_id.in_(enrolled),
                               Announcement.target_department == user_department))

    # For staff, also include sent announcements targeting their courses
    if user_type in ("DR", "TA"):
        from app.models.material import MaterialTeacher
        taught = db.query(MaterialTeacher.material_id).filter(MaterialTeacher.user_id == user_id).scalar_subquery()
        conditions.append(and_(Announcement.target_type == "course",
                               Announcement.target_course_id.in_(taught)))
        conditions.append(and_(Announcement.target_type == "course_department",
                               Announcement.target_course_id.in_(taught),
                               Announcement.target_department == user_department))

    # explicit multi-user targeting: match by announcement_id stored in join table
    targeted_ann_ids = db.query(AnnouncementTargetUser.announcement_id).filter(
        AnnouncementTargetUser.user_id == user_id
    ).scalar_subquery()

    query = (
        db.query(Announcement)
          .filter(
              or_(
                  *conditions,
                  Announcement.announcement_id.in_(targeted_ann_ids),
              )
          )
    )

    if target_course_id:
        query = query.filter(Announcement.target_course_id == target_course_id)
    if announcement_type:
        query = query.filter(Announcement.announcement_type == announcement_type)
    if priority:
        query = query.filter(Announcement.priority == priority)
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(Announcement.title.ilike(like), Announcement.content.ilike(like))
        )
    if unread_only:
        read_ids = db.query(AnnouncementRead.announcement_id).filter(
            AnnouncementRead.user_id == user_id
        ).subquery()
        query = query.filter(Announcement.announcement_id.notin_(read_ids))

    announcements = (
        query.order_by(Announcement.created_at.desc())
             .offset(skip)
             .limit(limit)
             .all()
    )
    return [_enrich_announcement(db, a, user_id) for a in announcements]




def get_sent_announcements(
    db: Session,
    author_id: int,
    *,
    skip: int = 0,
    limit: int = 50,
) -> list[dict]:
    announcements = (
        db.query(Announcement)
          .filter(Announcement.author_id == author_id)
          .order_by(Announcement.created_at.desc())
          .offset(skip)
          .limit(limit)
          .all()
    )
    return [_enrich_announcement(db, a, author_id) for a in announcements]


def get_unread_count(db: Session, user_id: int, user_type: str, user_level: int, user_department: Optional[str]) -> int:
    items = get_announcements_for_user(
        db, user_id, user_type, user_level, user_department, unread_only=True, limit=1000
    )
    return len(items)


def mark_announcement_read(db: Session, announcement_id: int, user_id: int) -> None:
    ann = get_announcement(db, announcement_id)  # raises 404 if not found
    _mark_as_read(db, announcement_id, user_id)


def create_announcement(db: Session, data: AnnouncementCreate, author_id: int) -> dict:
    author = get_user_info(db, author_id)
    if author.type_code not in ("ADM", "DR", "TA"):
        raise HTTPException(status_code=403, detail="Not authorized to create announcements")

    payload = data.model_dump(exclude={"target_user_ids"})
    announcement = Announcement(**payload, author_id=author_id)
    db.add(announcement)
    db.flush()  # get announcement_id before commit

    # Save explicit recipient list
    if data.target_type == "users" and data.target_user_ids:
        for uid in set(data.target_user_ids):
            db.add(AnnouncementTargetUser(announcement_id=announcement.announcement_id, user_id=uid))

    db.commit()
    db.refresh(announcement)
    _mark_as_read(db, announcement.announcement_id, author_id)

    from app.services.notification_service import notify_announcement
    notify_announcement(db, announcement, author_id)

    return _enrich_announcement(db, announcement, author_id)


def update_announcement(db: Session, announcement_id: int, data: AnnouncementUpdate, user_id: int) -> dict:
    announcement = get_announcement(db, announcement_id)
    _check_can_manage(db, announcement, user_id)

    # Apply scalar fields (excludes target_user_ids which lives in a join table)
    scalar = data.model_dump(exclude_unset=True, exclude={"target_user_ids"})
    for field, value in scalar.items():
        setattr(announcement, field, value)

    # Rebuild explicit recipient list when provided
    if data.target_user_ids is not None:
        db.query(AnnouncementTargetUser).filter(
            AnnouncementTargetUser.announcement_id == announcement_id
        ).delete(synchronize_session=False)
        if data.target_user_ids:
            for uid in set(data.target_user_ids):
                db.add(AnnouncementTargetUser(
                    announcement_id=announcement_id, user_id=uid
                ))

    db.commit()
    db.refresh(announcement)
    return _enrich_announcement(db, announcement, user_id)


def delete_announcement(db: Session, announcement_id: int, user_id: int) -> None:
    announcement = get_announcement(db, announcement_id)
    _check_can_manage(db, announcement, user_id)  # author or admin
    # Remove linked file records for material-file announcements so they don't
    # become invisible orphans after the announcement wrapper is gone.
    if announcement.announcement_type == 'material_file':
        db.query(MaterialFile).filter(
            MaterialFile.announcement_id == announcement_id
        ).delete(synchronize_session=False)
    db.delete(announcement)
    db.commit()


# ── Recipient listing ─────────────────────────────────────────────────────────

def get_available_recipients(
    db: Session,
    requester_id: int,
    *,
    role_filter: Optional[str] = None,
    course_id: Optional[str] = None,
    department: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> list:
    from app.models.user import User
    from app.models.material import MaterialTeacher, MaterialStudent

    requester = get_user_info(db, requester_id)
    query = db.query(User).filter(User.user_id != requester_id)

    if requester.type_code == "ADM":
        # Admins can target anyone
        pass
    elif requester.type_code in ("DR", "TA"):
        # DR/TA can only target students in their courses
        taught_ids = db.query(MaterialTeacher.material_id).filter(
            MaterialTeacher.user_id == requester_id
        ).subquery()
        enrolled_user_ids = db.query(MaterialStudent.user_id).filter(
            MaterialStudent.material_id.in_(taught_ids)
        ).subquery()
        if course_id:
            # narrow to specific course
            specific_enrolled = db.query(MaterialStudent.user_id).filter(
                MaterialStudent.material_id == course_id
            ).subquery()
            query = query.filter(User.user_id.in_(specific_enrolled))
        else:
            query = query.filter(User.user_id.in_(enrolled_user_ids))
    elif requester.type_code == "STU":
        # Students can only target DR/TA of their enrolled courses
        enrolled_material_ids = db.query(MaterialStudent.material_id).filter(
            MaterialStudent.user_id == requester_id
        ).subquery()
        staff_ids = db.query(MaterialTeacher.user_id).filter(
            MaterialTeacher.material_id.in_(enrolled_material_ids)
        ).subquery()
        query = query.filter(
            User.user_id.in_(staff_ids),
            User.type_code.in_(["DR", "TA"]),
        )
    else:
        raise HTTPException(status_code=403, detail="Not authorized to search recipients")

    if role_filter:
        query = query.filter(User.type_code == role_filter)
    if department:
        query = query.filter(User.department == department)
    if search:
        # name: substring match; uni_code: prefix match to avoid overly broad ID results
        query = query.filter(or_(
            User.name.ilike(f"%{search}%"),
            User.uni_code.ilike(f"{search}%"),
        ))

    return query.offset(skip).limit(limit).all()
