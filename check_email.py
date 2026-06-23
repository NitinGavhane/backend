from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
email = "gavhanenitin911@gmail.com"
r = db.execute(
    text("SELECT id, email, full_name, role, is_verified FROM users WHERE LOWER(email) = LOWER(:e)"),
    {"e": email}
).fetchone()
if r:
    print(f'FOUND: id={r[0]}, email={r[1]}, name={r[2]}, role={r[3]}, verified={r[4]}')
else:
    print('NOT FOUND')
db.close()
