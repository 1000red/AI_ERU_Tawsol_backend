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

        existing = {m.material_id for m in db.query(Material.material_id).all()}

        new_materials = [
            Material(
                material_id     = row["material_id"],
                name            = row["name"],
                description     = row["description"] or None,
                duration        = int(row["duration"]),
                profile_picture = row["profile_picture"] or None,
            )
            for row in rows
            if row["material_id"] not in existing
        ]

        db.add_all(new_materials)
        db.commit()
        print(f"Done: {len(new_materials)} added, {len(rows) - len(new_materials)} skipped.")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_materials()
