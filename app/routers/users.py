from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.schemas.user import UserOut, UserUpdate, ChangePasswordRequest
from app.services import user_service as svc

router = APIRouter(prefix="/users", tags=["Users"])


# ── Current user ──────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserOut)
def get_me(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return svc.get_user_by_id(db, user_id)


@router.put("/me", response_model=UserOut)
def update_me(
    data: UserUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return svc.update_user(db, user_id, data)


@router.put("/me/password")
def change_password(
    data: ChangePasswordRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    svc.change_password(db, user_id, data.old_password, data.new_password)
    return {"message": "Password changed successfully"}



# ── General ───────────────────────────────────────────────────────────────────

@router.get("/types/all")
def get_user_types(db: Session = Depends(get_db)):
    return svc.get_user_types(db)


@router.get("/", response_model=list[UserOut])
def list_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return svc.get_all_users(db, skip, limit)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    return svc.get_user_by_id(db, user_id)