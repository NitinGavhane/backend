import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
from sqlalchemy import text
from app.core.database import SessionLocal

db = SessionLocal()
for t in ["orders", "referral_earnings", "cart_items", "users", "payments"]:
    cols = db.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name=:t AND table_schema='public'"
        ),
        {"t": t},
    ).fetchall()
    print(t, "->", sorted(c[0] for c in cols))
db.close()