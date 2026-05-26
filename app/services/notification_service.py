from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import HTTPException
from typing import Optional

from app.models.notification import AppNotification


# ── Internal helpers ──────────────────────────────────────────────────────────

def _resolve_announcement_recipients(db: Session, announcement) -> list[int]:
    """Return user IDs that should be notified for a given Announcement object."""
    from app.models.user import User
    from app.models.material import MaterialStudent
    from app.models.content.announcement import AnnouncementTargetUser

    ttype = announcement.target_type

    if ttype == "users":
        return [r.user_id for r in
                db.query(AnnouncementTargetUser.user_id)
                  .filter(AnnouncementTargetUser.announcement_id == announcement.announcement_id)
                  .all()]

    if ttype == "student" and announcement.target_student_id:
        return [announcement.target_student_id]

    q = db.query(User.user_id)

    if ttype == "all":
        return [r[0] for r in q.all()]

    if ttype == "department":
        return [r[0] for r in q.filter(User.department == announcement.target_department).all()]

    if ttype == "level":
        q = q.filter(User.level == announcement.target_year)
        if announcement.target_department:
            q = q.filter(User.department == announcement.target_department)
        return [r[0] for r in q.all()]

    if ttype in ("course", "course_department"):
        enrolled = db.query(MaterialStudent.user_id).filter(
            MaterialStudent.material_id == announcement.target_course_id
        )
        if ttype == "course_department" and announcement.target_department:
            enrolled = enrolled.join(User, User.user_id == MaterialStudent.user_id).filter(
                User.department == announcement.target_department
            )
        return [r[0] for r in enrolled.all()]

    return []


# ── Core operations ───────────────────────────────────────────────────────────

def notify_announcement(
    db: Session,
    announcement,
    author_id: int,
) -> None:
    """Create an AppNotification row for every recipient of an announcement."""
    recipient_ids = _resolve_announcement_recipients(db, announcement)
    recipient_ids = [uid for uid in recipient_ids if uid != author_id]
    if not recipient_ids:
        return

    db.bulk_insert_mappings(
        AppNotification,
        [
            {
                "user_id":    uid,
                "title":      announcement.title,
                "body":       announcement.content[:200] if announcement.content else None,
                "notif_type": "announcement",
                "ref_id":     announcement.announcement_id,
                "is_read":    False,
            }
            for uid in recipient_ids
        ],
    )
    db.commit()


def notify_assignment(
    db: Session,
    assignment,
    course_name: Optional[str] = None,
) -> None:
    """Notify all students enrolled in the assignment's material."""
    from app.models.material import MaterialStudent

    enrolled_ids = [
        r[0] for r in
        db.query(MaterialStudent.user_id)
          .filter(MaterialStudent.material_id == assignment.material_id)
          .all()
    ]
    if not enrolled_ids:
        return

    subject = f" — {course_name}" if course_name else ""
    db.bulk_insert_mappings(
        AppNotification,
        [
            {
                "user_id":    uid,
                "title":      f"New Assignment{subject}",
                "body":       assignment.title,
                "notif_type": "assignment",
                "ref_id":     assignment.assignment_id,
                "is_read":    False,
            }
            for uid in enrolled_ids
            if uid != assignment.author_id
        ],
    )
    db.commit()


# ── Queries ───────────────────────────────────────────────────────────────────

def get_notifications(
    db: Session,
    user_id: int,
    *,
    unread_only: bool = False,
    notif_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[AppNotification]:
    q = db.query(AppNotification).filter(AppNotification.user_id == user_id)
    if unread_only:
        q = q.filter(AppNotification.is_read == False)
    if notif_type:
        q = q.filter(AppNotification.notif_type == notif_type)
    return q.order_by(AppNotification.created_at.desc()).offset(skip).limit(limit).all()


def get_unread_count(db: Session, user_id: int) -> int:
    return (
        db.query(AppNotification)
          .filter(AppNotification.user_id == user_id, AppNotification.is_read == False)
          .count()
    )


def mark_read(db: Session, notification_id: int, user_id: int) -> AppNotification:
    notif = db.query(AppNotification).filter(
        AppNotification.id == notification_id,
        AppNotification.user_id == user_id,
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif


def mark_all_read(db: Session, user_id: int) -> int:
    """Mark every unread notification as read. Returns count updated."""
    updated = (
        db.query(AppNotification)
          .filter(AppNotification.user_id == user_id, AppNotification.is_read == False)
          .update({"is_read": True}, synchronize_session=False)
    )
    db.commit()
    return updated


def delete_notification(db: Session, notification_id: int, user_id: int) -> None:
    notif = db.query(AppNotification).filter(
        AppNotification.id == notification_id,
        AppNotification.user_id == user_id,
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    db.delete(notif)
    db.commit()
