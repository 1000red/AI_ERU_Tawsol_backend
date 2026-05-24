import csv
from app.db.database import SessionLocal
from app.models.user import User
from app.core.security import hash_password

CSV_FILE_PATH = "app/db/add_db/source/eru_students.csv"

def seed_students():
    db = SessionLocal()
    try:
        with open(CSV_FILE_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        existing = {u.uni_code for u in db.query(User.uni_code).all()}

        new_students = [
            User(
                uni_code             = row["uni_code"],
                name                 = row["name"],
                email                = row["email"],
                password             = hash_password(row["password"]),
                level                = int(row["level"]),
                department           = row["department"],
                type_code            = row["type_code"],
                current_password = True,
            )
            for row in rows
            if row["uni_code"] not in existing
        ]

        db.add_all(new_students)
        db.commit()
        print(f"Done: {len(new_students)} added, {len(rows) - len(new_students)} skipped.")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_students()
