from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

mappings = [
    ("men", ["footware", "shirts", "kurtas", "casuals", "jeans", "formal wear"]),
    ("women", ["women footwear", "western wear", "top&skirt", "dress", "sarees", "ethnic wear", "western dress", "co-ord set"]),
    ("kids", []),
]

for gender, names in mappings:
    for name in names:
        db.execute(
            text("UPDATE categories SET gender = :gender WHERE LOWER(TRIM(name)) = :name AND gender IS DISTINCT FROM :gender"),
            {"gender": gender, "name": name},
        )

db.execute(
    text("UPDATE categories SET gender = 'unisex' WHERE TRIM(COALESCE(gender, '')) = ''"),
)
db.commit()

rows = db.execute(text("SELECT name, gender FROM categories ORDER BY name")).fetchall()
print("Updated categories:")
for r in rows:
    print(f"  {r[0]:25s} → {r[1]}")

db.close()
