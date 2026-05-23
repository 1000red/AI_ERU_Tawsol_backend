from sqlalchemy.orm import Session
from fastapi import HTTPException


def get_user_info(db: Session, user_id: int):
    from app.models.user import User
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _check_author(obj, user_id: int):
    if obj.author_id != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")
