from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("")
def list_notifications(
    unread_only: bool = Query(False),
    notif_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return notification_service.get_notifications(
        db,
        user_id,
        unread_only=unread_only,
        notif_type=notif_type,
        skip=skip,
        limit=limit,
    )


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    count = notification_service.get_unread_count(db, user_id)
    return {"unread_count": count}


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return notification_service.mark_read(db, notification_id, user_id)


@router.post("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    updated = notification_service.mark_all_read(db, user_id)
    return {"marked_read": updated}


@router.delete("/{notification_id}")
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    notification_service.delete_notification(db, notification_id, user_id)
    return {"detail": "Notification deleted"}
