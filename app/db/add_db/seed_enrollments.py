from app.db.database import SessionLocal
from app.models.material import MaterialStudent

ENROLLMENTS = [
    {"user_id": 1386, "material_id": "CS307"},  # Alfred Ayman → Computer Graphics
    {"user_id": 1382, "material_id": "DS305"},  # Ziad Tamer  → Fundamentals of Simulation
    {"user_id": 1382, "material_id": "CB302"},  # Ziad Tamer  → Computer Architecture
]


def seed():
    db = SessionLocal()
    try:
        for e in ENROLLMENTS:
            exists = db.query(MaterialStudent).filter(
                MaterialStudent.user_id     == e["user_id"],
                MaterialStudent.material_id == e["material_id"],
            ).first()
            if not exists:
                db.add(MaterialStudent(user_id=e["user_id"], material_id=e["material_id"]))
                print(f"Enrolled user {e['user_id']} in {e['material_id']}")
            else:
                print(f"Already enrolled: user {e['user_id']} in {e['material_id']}")

        db.commit()
        print("Done.")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
