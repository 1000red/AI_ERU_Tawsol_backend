from app.db.database import SessionLocal
from app.models.material import MaterialStudent

# ENROLLMENTS = [
#     {"user_id": 1386, "material_id": "CS307"},  # Alfred Ayman → Computer Graphics
#     {"user_id": 1382, "material_id": "DS305"},  # Ziad Tamer  → Fundamentals of Simulation
#     {"user_id": 1382, "material_id": "CB302"},  # Ziad Tamer  → Computer Architecture
# ]

ENROLLMENTS = [
    {"user_id": 1455, "material_id": "CS307"},
    {"user_id": 1843, "material_id": "CS307"},
    {"user_id": 1460, "material_id": "CS307"},
    {"user_id": 1844, "material_id": "CS307"},
    {"user_id": 1477, "material_id": "CS307"},
    {"user_id": 1845, "material_id": "CS307"},
    {"user_id": 1846, "material_id": "CS307"},
    {"user_id": 1398, "material_id": "CS307"},
    {"user_id": 1838, "material_id": "CS307"},
    {"user_id": 1361, "material_id": "CS307"},
    {"user_id": 1360, "material_id": "CS307"},
    # for uid in range(1837, 2059)
]

def seed():
    db = SessionLocal()

    already_enrolled_count = 0
    new_enrolled_count = 0
    
    try:
        for e in ENROLLMENTS:
            exists = db.query(MaterialStudent).filter(
                MaterialStudent.user_id     == e["user_id"],
                MaterialStudent.material_id == e["material_id"],
            ).first()
            if not exists:
                db.add(MaterialStudent(user_id=e["user_id"], material_id=e["material_id"]))
                print(f"Enrolled user {e['user_id']} in {e['material_id']}")
                new_enrolled_count += 1
            else:
                print(f"Already enrolled: user {e['user_id']} in {e['material_id']}")
                already_enrolled_count += 1

        db.commit()
        print("---")
        print(f"Done. New enrollments: {new_enrolled_count}, Already enrolled: {already_enrolled_count}")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()