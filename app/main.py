import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from app.api import admin, auth, cart, categories, orders, payments, products, referral, wallet
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Base.metadata.create_all(bind=engine)
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


@app.get("/")
def root():
    return {"message": "Garment E-commerce Platform API", "version": settings.APP_VERSION, "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "healthy"}
