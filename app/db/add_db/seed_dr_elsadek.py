import uuid
from app.db.database import SessionLocal
from app.models.user import User
from app.models.material import Material, MaterialTeacher
from app.core.security import hash_password

PROFESSOR = {
    "uni_code"  : str(uuid.uuid4())[:8],
    "name"      : "Elsadek Hussien",
    "email"     : "elsadek-hussien@eru.edu.eg",
    "password"  : "123456",
    "level"     : 100,
    "type_code" : "DR",
}

MATERIALS = [
    {"material_id": "CS307", "name": "Computer Graphics",         "duration": 3},
    {"material_id": "DS305", "name": "Fundamentals of Simulation", "duration": 3},
    {"material_id": "CB302", "name": "Computer Architecture",     "duration": 3},
]


def seed():
    db = SessionLocal()
    try:
        # 1. Add missing materials
        for m in MATERIALS:
            if not db.query(Material).filter(Material.material_id == m["material_id"]).first():
                db.add(Material(material_id=m["material_id"], name=m["name"], duration=m["duration"]))
                print(f"Added material: {m['material_id']} - {m['name']}")

        db.flush()

        # 2. Add professor
        professor = db.query(User).filter(User.email == PROFESSOR["email"]).first()
        if not professor:
            professor = User(
                uni_code  = PROFESSOR["uni_code"],
                name      = PROFESSOR["name"],
                email     = PROFESSOR["email"],
                password  = hash_password(PROFESSOR["password"]),
                level     = PROFESSOR["level"],
                type_code = PROFESSOR["type_code"],
            )
            db.add(professor)
            db.flush()
            print(f"Added professor: {professor.name}")
        else:
            print(f"Professor already exists: {professor.name}")

        # 3. Link professor to materials
        for m in MATERIALS:
            exists = db.query(MaterialTeacher).filter(
                MaterialTeacher.material_id == m["material_id"],
                MaterialTeacher.user_id    == professor.user_id,
            ).first()
            if not exists:
                db.add(MaterialTeacher(material_id=m["material_id"], user_id=professor.user_id))
                print(f"Linked to: {m['material_id']}")

        db.commit()
        print("Done.")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
