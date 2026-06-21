import ssl

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = True
ssl_context.verify_mode = ssl.CERT_REQUIRED

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"ssl_context": ssl_context},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


_tables_initialized = False


def ensure_tables():
    global _tables_initialized
    if _tables_initialized:
        return
    from app.models.address import Address
    from app.models.banner import Banner
    from app.models.blog import BlogPost
    from app.models.referral import ReferralEarning, ReferralShareClick
    from app.models.review import Review
    from app.models.wishlist import WishlistItem
    Base.metadata.create_all(bind=engine)
    try:
        db = SessionLocal()
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        user_columns = [c["name"] for c in inspector.get_columns("users")] if "users" in tables else []
        if "avatar_url" not in user_columns:
            db.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500)"))
        order_columns = [c["name"] for c in inspector.get_columns("orders")] if "orders" in tables else []
        if "return_reason" not in order_columns:
            db.execute(text("ALTER TABLE orders ADD COLUMN return_reason TEXT"))
            db.execute(text("ALTER TABLE orders ADD COLUMN return_status VARCHAR(20)"))
        db.commit()
        db.close()
    except Exception as e:
        print(f"Migration warning (non-fatal): {e}")
    _tables_initialized = True


def get_db():
    ensure_tables()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
