from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.schemas.content import AnnouncementCreate, AnnouncementUpdate, AnnouncementOut
from app.services import content_service as svc

router = APIRouter(prefix="/announcements", tags=["Announcements"])


@router.get("", response_model=list[AnnouncementOut])
def get_announcements(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = svc.get_user_info(db, user_id)
    return svc.get_announcements_for_user(
        db,
        user_id=user_id,
        user_type=user.type_code,
        user_level=user.level,
        user_department=user.department,
    )


@router.post("", response_model=AnnouncementOut, status_code=201)
def create_announcement(
    data: AnnouncementCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return svc.create_announcement(db, data, user_id)


@router.put("/{announcement_id}", response_model=AnnouncementOut)
def update_announcement(
    announcement_id: int,
    data: AnnouncementUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return svc.update_announcement(db, announcement_id, data, user_id)


@router.delete("/{announcement_id}", status_code=204)
def delete_announcement(
    announcement_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    svc.delete_announcement(db, announcement_id, user_id)
