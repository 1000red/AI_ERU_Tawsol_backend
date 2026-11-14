from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.models.user import User
from app.models.contact import ContactMessage
from app.schemas.support import ContactRequest
from app.utils.email import send_contact_us_email

router = APIRouter(prefix="/contact", tags=["Support"])


@router.post("", status_code=status.HTTP_200_OK)
@router.post("/", status_code=status.HTTP_200_OK)
def contact_us(
    data: ContactRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # 1. Persist complaint / support message in PostgreSQL database
    new_message = ContactMessage(
        user_id=user.user_id,
        user_name=user.name,
        user_email=user.email,
        issue_type=data.issue_type.value,
        subject=data.subject.strip(),
        message=data.message.strip(),
        status="open",
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message)

    # 2. Attempt to send email via SMTP gracefully if configured
    email_sent = False
    try:
        email_sent = send_contact_us_email(
            user_name=user.name,
            user_email=user.email,
            issue_type=data.issue_type.value,
            subject=data.subject.strip(),
            message=data.message.strip(),
        )
    except Exception as e:
        print(f"[ContactUs] Could not deliver email via SMTP: {e}")

    return {
        "detail": "تم إرسال الشكوى / الرسالة بنجاح وسنقوم بالرد عليك في أقرب وقت.",
        "id": new_message.id,
        "saved": True,
        "email_sent": bool(email_sent),
    }


@router.get("/my", status_code=status.HTTP_200_OK)
@router.get("/my/", status_code=status.HTTP_200_OK)
def get_my_contact_messages(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    messages = (
        db.query(ContactMessage)
        .filter(ContactMessage.user_id == user_id)
        .order_by(ContactMessage.created_at.desc())
        .all()
    )
    return [
        {
            "id": m.id,
            "issue_type": m.issue_type,
            "subject": m.subject,
            "message": m.message,
            "status": m.status,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]
