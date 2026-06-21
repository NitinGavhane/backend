import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from app.api import admin, addresses, auth, blog, cart, categories, home, orders, payment_methods, payments, products, referral, reviews, wallet, wishlist
from app.core.config import settings
from app.core.database import SessionLocal, engine, ensure_tables
from app.core.security import hash_password
from app.models.user import User


def _run_migrations(db: Session):
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("categories")]

    if "gender" not in columns:
        db.execute(text("ALTER TABLE categories ADD COLUMN gender VARCHAR(20) NOT NULL DEFAULT 'unisex'"))
        print("Migration: added gender column to categories")

    db.execute(text("""
        UPDATE categories SET gender = 'men'
        WHERE LOWER(TRIM(name)) IN ('men', 'footwear', 'kurtas', 'shirts')
          AND gender IS DISTINCT FROM 'men'
    """))
    db.execute(text("""
        UPDATE categories SET gender = 'women'
        WHERE LOWER(TRIM(name)) = 'women'
          AND gender IS DISTINCT FROM 'women'
    """))
    db.execute(text("""
        UPDATE categories SET gender = 'kids'
        WHERE LOWER(TRIM(name)) = 'kids'
          AND gender IS DISTINCT FROM 'kids'
    """))
    db.commit()
    print("Migration: category genders synced [men→Men/Footwear/Kurtas/Shirts, women→Women, kids→Kids]")

    product_columns = [c["name"] for c in inspector.get_columns("products")]
    if "gender" not in product_columns:
        db.execute(text("ALTER TABLE products ADD COLUMN gender VARCHAR(20) NOT NULL DEFAULT 'unisex'"))
        print("Migration: added gender column to products")

    db.execute(text("""
        UPDATE products p
        SET gender = c.gender
        FROM categories c
        WHERE p.category_id = c.id
          AND p.gender IS DISTINCT FROM c.gender
    """))
    db.commit()
    print("Migration: product genders synced from categories")

    user_columns = [c["name"] for c in inspector.get_columns("users")]
    if "avatar_url" not in user_columns:
        db.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500)"))
        print("Migration: added avatar_url column to users")

    user_columns = [c["name"] for c in inspector.get_columns("users")]
    if "otp_code" not in user_columns:
        db.execute(text("ALTER TABLE users ADD COLUMN otp_code VARCHAR(6)"))
        db.execute(text("ALTER TABLE users ADD COLUMN otp_expires_at TIMESTAMP WITH TIME ZONE"))
        print("Migration: added otp_code and otp_expires_at columns to users")

    order_columns = [c["name"] for c in inspector.get_columns("orders")]
    if "return_reason" not in order_columns:
        db.execute(text("ALTER TABLE orders ADD COLUMN return_reason TEXT"))
        db.execute(text("ALTER TABLE orders ADD COLUMN return_status VARCHAR(20)"))
        print("Migration: added return_reason and return_status columns to orders")

    tables = inspector.get_table_names()
    referral_earnings_exists = "referral_earnings" in tables
    referral_columns = [c["name"] for c in inspector.get_columns("referral_earnings")] if referral_earnings_exists else []
    if "product_id" not in referral_columns:
        db.execute(text("ALTER TABLE referral_earnings ADD COLUMN product_id UUID REFERENCES products(id)"))
        db.execute(text("ALTER TABLE referral_earnings ADD COLUMN purchase_amount FLOAT DEFAULT 0"))
        db.execute(text("ALTER TABLE referral_earnings ADD COLUMN reward_amount FLOAT DEFAULT 0"))
        db.execute(text("ALTER TABLE referral_earnings ADD COLUMN reward_percentage FLOAT DEFAULT 0"))
        db.execute(text("ALTER TABLE referral_earnings ADD COLUMN approved_at TIMESTAMP WITH TIME ZONE"))
        db.execute(text("ALTER TABLE referral_earnings ALTER COLUMN commission_amount DROP NOT NULL"))
        print("Migration: added referral tracking columns to referral_earnings")

    if referral_earnings_exists:
        try:
            db.execute(text("ALTER TYPE reward_status ADD VALUE 'approved'"))
        except Exception:
            pass
        try:
            db.execute(text("ALTER TYPE reward_status ADD VALUE 'rejected'"))
        except Exception:
            pass

    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ensure_tables()
        db: Session = SessionLocal()
        try:
            _run_migrations(db)
            admin_user = db.query(User).filter(User.role == "admin").first()
            if not admin_user:
                admin_user = User(
                    full_name="Admin",
                    email="admin@garment.com",
                    password_hash=hash_password("Admin@1234"),
                    role="admin",
                    referral_code="ADMIN000",
                    is_verified=True,
                )
                db.add(admin_user)
                db.commit()
                print("Admin user seeded: admin@garment.com / Admin@1234")
        finally:
            db.close()
    except Exception as e:
        print(f"DB init skipped (first request will retry): {e}")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend API for Garment E-commerce Platform — User & Admin endpoints",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Admin", "description": "Admin operations — dashboard, user management, product & category CRUD"},
        {"name": "Authentication", "description": "User login, registration, token refresh"},
        {"name": "Products", "description": "Product listing and retrieval"},
        {"name": "Categories", "description": "Category listing and retrieval"},
        {"name": "Cart", "description": "Cart management — add, update, remove items"},
        {"name": "Orders", "description": "Order creation and history"},
        {"name": "Payments", "description": "Payment processing and verification"},
        {"name": "Referral", "description": "Referral code and earnings management"},
        {"name": "Wallet", "description": "Wallet balance and transactions"},
        {"name": "Addresses", "description": "User address book management"},
        {"name": "Wishlist", "description": "User wishlist management"},
        {"name": "Reviews", "description": "Product reviews and ratings"},
        {"name": "Blog", "description": "Blog posts listing"},
        {"name": "Home", "description": "Home page content (banners, featured products)"},
        {"name": "Payment Methods", "description": "Available payment methods"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(categories.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(referral.router)
app.include_router(wallet.router)
app.include_router(admin.router)
app.include_router(addresses.router)
app.include_router(wishlist.router)
app.include_router(reviews.router)
app.include_router(blog.router)
app.include_router(home.router)
app.include_router(payment_methods.router)


@app.get("/")
def root():
    return {"message": "Garment E-commerce Platform API", "version": settings.APP_VERSION, "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "healthy"}
