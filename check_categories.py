from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
rows = db.execute(text("SELECT name, gender FROM categories ORDER BY name")).fetchall()
print(f"DB host from config: check below")
print("Categories in DB:")
for r in rows:
    print(f"  '{r[0]}' -> '{r[1]}'")
db.close()
