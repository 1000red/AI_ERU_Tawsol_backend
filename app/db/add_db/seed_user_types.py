from app.db.database import SessionLocal
from app.models.user import UserType


def seed_user_types():
    db = SessionLocal()
    try:
        user_types = [
            UserType(code="STU", description="Student"),
            UserType(code="DR",  description="Professor"),
            UserType(code="TA",  description="Teaching Assistant"),
            UserType(code="ADM", description="Admin"),
        ]

        for ut in user_types:
            exists = db.query(UserType).filter(UserType.code == ut.code).first()
            if not exists:
                db.add(ut)

        db.commit()
        print("UserType seed done.")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_user_types()
