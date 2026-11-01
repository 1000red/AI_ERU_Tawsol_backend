from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.models.user import User
from app.schemas.support import ContactRequest
from app.utils.email import send_contact_us_email

router = APIRouter(prefix="/contact", tags=["Support"])


@router.post("/", status_code=status.HTTP_200_OK)
def contact_us(
    data: ContactRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    sent = send_contact_us_email(
        user_name=user.name,
        user_email=user.email,
        issue_type=data.issue_type.value,
        subject=data.subject,
        message=data.message,
    )

    if not sent:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send email. Please try again later.")

    return {"detail": "message has been successfully sent. We will respond to you as soon as possible"}
