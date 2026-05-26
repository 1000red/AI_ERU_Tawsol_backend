import csv
from app.db.database import SessionLocal
from app.models.material import Material

CSV_FILE_PATH = "app/db/add_db/source/eru_material.csv"

def seed_materials():
    db = SessionLocal()
    try:
        with open(CSV_FILE_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        existing = {m.material_id: m for m in db.query(Material).all()}

        added = 0
        updated = 0
        for row in rows:
            dept = row["department_course"]
            if row["material_id"] not in existing:
                db.add(Material(
                    material_id       = row["material_id"],
                    name              = row["name"],
                    description       = row["description"] or None,
                    duration          = int(row["duration"]),
                    department_course = dept,
                ))
                added += 1
            else:
                mat = existing[row["material_id"]]
                mat.name              = row["name"]
                mat.description       = row["description"] or None
                mat.duration          = int(row["duration"])
                mat.department_course = dept
                updated += 1

        db.commit()
        print(f"Done: {added} added, {updated} updated.")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_materials()
