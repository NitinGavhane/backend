import ssl
from urllib.parse import urlparse

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

_connect_args: dict = {}
parsed = urlparse(settings.db_url)
if parsed.scheme.endswith("+pg8000") and parsed.hostname != "localhost":
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        _connect_args["ssl_context"] = ctx
    except Exception:
        try:
            ctx = ssl._create_unverified_context()
            _connect_args["ssl_context"] = ctx
        except Exception:
            pass

# pool_pre_ping validates each pooled connection with a lightweight liveness
# check before use, so a connection Neon dropped during idle (common on
# Vercel serverless cold starts) is transparently reconnected instead of
# surfacing as a 500 on the first request. pool_recycle proactively retires
# connections older than 5 min, staying under Neon's idle-disconnect window.
_engine_kwargs = dict(echo=settings.DEBUG, pool_pre_ping=True, pool_recycle=300)
if _connect_args:
    engine = create_engine(settings.db_url, connect_args=_connect_args, **_engine_kwargs)
else:
    engine = create_engine(settings.db_url, **_engine_kwargs)
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
    from app.models.delivery import DeliverySettings
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
        if "delivery_fee" not in order_columns:
            db.execute(text("ALTER TABLE orders ADD COLUMN delivery_fee FLOAT DEFAULT 0.0"))
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
