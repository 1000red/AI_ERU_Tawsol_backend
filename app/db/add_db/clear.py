from app.db.database import SessionLocal, engine
from app.db import base  # noqa: F401

db = SessionLocal()
try:
    for table in reversed(base.Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    print("Done.")
finally:
    db.close()
