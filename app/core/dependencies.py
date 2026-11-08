from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.services import user_service as svc


from app.models.user import User


def get_current_user(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> User:
    return svc.get_user_by_id(db, user_id)


def require_admin(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = svc.get_user_by_id(db, user_id)
    if user.type_code != "ADM":
        raise HTTPException(status_code=403, detail="Admins only")