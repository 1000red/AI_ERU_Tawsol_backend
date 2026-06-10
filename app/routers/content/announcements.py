from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.core.security import get_current_user_id, get_current_user_id_ws
from app.schemas.content import AnnouncementCreate, AnnouncementUpdate, AnnouncementOut
from app.schemas.content.announcement import RecipientOut, UnreadCountOut
from app.services import content_service as svc
from app.websockets import announcement_manager

router = APIRouter(prefix="/announcements", tags=["Announcements"])


# ── List & filtering ──────────────────────────────────────────────────────────

@router.get("", response_model=list[AnnouncementOut])
def get_announcements(
    announcement_type: Optional[str] = Query(None, description="normal | material_file | assignment"),
    priority:          Optional[str] = Query(None, description="normal | important | urgent"),
    target_course_id:  Optional[str] = Query(None, description="Filter by course/material ID"),
    unread_only:       bool          = Query(False),
    search:            Optional[str] = Query(None),
    skip:              int           = Query(0, ge=0),
    limit:             int           = Query(50, ge=1, le=200),
    user_id: int      = Depends(get_current_user_id),
    db: Session       = Depends(get_db),
):
    user = svc.get_user_info(db, user_id)
    return svc.get_announcements_for_user(
        db,
        user_id=user_id,
        user_type=user.type_code,
        user_level=user.level,
        user_department=user.department,
        announcement_type=announcement_type,
        priority=priority,
        target_course_id=target_course_id,
        unread_only=unread_only,
        search=search,
        skip=skip,
        limit=limit,
    )


@router.get("/unread-count", response_model=UnreadCountOut)
def get_unread_count(
    user_id: int  = Depends(get_current_user_id),
    db: Session   = Depends(get_db),
):
    user = svc.get_user_info(db, user_id)
    count = svc.get_unread_count(db, user_id, user.type_code, user.level, user.department)
    return {"unread_count": count}


@router.get("/sent", response_model=list[AnnouncementOut])
def get_sent_announcements(
    skip:  int  = Query(0, ge=0),
    limit: int  = Query(50, ge=1, le=200),
    user_id: int = Depends(get_current_user_id),
    db: Session  = Depends(get_db),
):
    user = svc.get_user_info(db, user_id)
    if user.type_code not in ("ADM", "DR", "TA"):
        return []
    return svc.get_sent_announcements(db, user_id, skip=skip, limit=limit)


@router.get("/recipients", response_model=list[RecipientOut])
def get_recipients(
    role:       Optional[str] = Query(None, description="STU | DR | TA | ADM"),
    course_id:  Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    search:     Optional[str] = Query(None),
    skip:       int           = Query(0, ge=0),
    limit:      int           = Query(100, ge=1, le=500),
    user_id: int  = Depends(get_current_user_id),
    db: Session   = Depends(get_db),
):
    return svc.get_available_recipients(
        db,
        requester_id=user_id,
        role_filter=role,
        course_id=course_id,
        department=department,
        search=search,
        skip=skip,
        limit=limit,
    )


# ── Single announcement detail ────────────────────────────────────────────────

@router.get("/{announcement_id}", response_model=AnnouncementOut)
def get_announcement(
    announcement_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session  = Depends(get_db),
):
    return svc.get_announcement_detail(db, announcement_id, user_id)


# ── Create / Update / Delete ──────────────────────────────────────────────────

@router.post("", response_model=AnnouncementOut, status_code=201)
def create_announcement(
    data: AnnouncementCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session  = Depends(get_db),
):
    return svc.create_announcement(db, data, user_id)


@router.put("/{announcement_id}", response_model=AnnouncementOut)
def update_announcement(
    announcement_id: int,
    data: AnnouncementUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session  = Depends(get_db),
):
    return svc.update_announcement(db, announcement_id, data, user_id)


@router.delete("/{announcement_id}", status_code=204)
def delete_announcement(
    announcement_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session  = Depends(get_db),
):
    svc.delete_announcement(db, announcement_id, user_id)


# ── Mark as read ──────────────────────────────────────────────────────────────

@router.post("/{announcement_id}/read", status_code=204)
def mark_as_read(
    announcement_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session  = Depends(get_db),
):
    svc.mark_announcement_read(db, announcement_id, user_id)


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws/{user_id}")
async def announcements_ws(
    websocket: WebSocket,
    user_id: int,
    token: str = Query(...),
):
    # Must accept() before any close() — otherwise Starlette returns 403 HTTP
    await websocket.accept()

    try:
        token_user_id = get_current_user_id_ws(token)
        if token_user_id != user_id:
            await websocket.close(code=4001, reason="Unauthorized")
            return
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    announcement_manager.connect(user_id, websocket)
    try:
        while True:
            # keep connection alive; client may send pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[AnnounWS] Error user {user_id}: {e}")
    finally:
        announcement_manager.disconnect(user_id)
