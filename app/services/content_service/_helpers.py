from sqlalchemy.orm import Session
from fastapi import HTTPException


def get_user_info(db: Session, user_id: int):
    from app.models.user import User
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _check_author(obj, user_id: int) -> None:
    """Legacy author-only check (kept for backward compat). Prefer _check_can_manage."""
    if obj.author_id != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")


def _check_can_manage(db: Session, obj, user_id: int) -> None:
    """Author OR admin can manage the object. Students are always rejected."""
    from app.models.user import User
    if obj.author_id == user_id:
        return
    user = db.query(User).filter(User.user_id == user_id).first()
    if user and user.type_code == "ADM":
        return
    raise HTTPException(status_code=403, detail="Not allowed")


def _require_staff(db: Session, user_id: int) -> None:
    """Reject students from creating content."""
    user = get_user_info(db, user_id)
    if user.type_code == "STU":
        raise HTTPException(
            status_code=403,
            detail="Students cannot create content",
        )
