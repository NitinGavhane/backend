import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from app.api import admin, addresses, auth, blog, cart, categories, contact, delivery, fulfillment, home, orders, payment_methods, payments, products, referral, reviews, uploads, wallet, wishlist
from app.core import storage
from app.core.config import settings
from app.core.database import SessionLocal, engine, ensure_tables
from app.core.security import hash_password
from app.models.user import User


# The methods the store opens with. Codes match the gateway's own method names
# so they can be handed straight to its checkout. Seeded once; after that the
# table is the source of truth and the Admin app owns it.
_DEFAULT_PAYMENT_METHODS = [
    ("upi", "UPI", "Pay using any UPI app", "IN", 0),
    ("card", "Credit / Debit Card", "Visa, Mastercard, RuPay & more", "*", 1),
    ("netbanking", "Net Banking", "All major banks supported", "IN", 2),
    ("wallet", "Wallets", "Paytm, PhonePe, Amazon Pay & more", "IN", 3),
    ("cod", "Cash on Delivery", "Pay in cash or UPI when your order arrives", "*", 4),
]


def _seed_payment_methods(db: Session):
    """Populate the methods table on first boot, so checkout is never empty.

    Seeds only when the table has no rows at all. Once it does, the table is the
    Admin app's to own: topping up per-missing-code would resurrect a method an
    admin had deliberately deleted, every single deploy.
    """
    if db.execute(text("SELECT count(*) FROM payment_methods")).scalar():
        return
    for code, name, description, regions, sort_order in _DEFAULT_PAYMENT_METHODS:
        gateway = "cod" if code == "cod" else "cashfree"
        db.execute(
            text("""
                INSERT INTO payment_methods (id, code, name, description, gateway, regions, is_active, sort_order, created_at)
                VALUES (gen_random_uuid(), :code, :name, :description, :gateway, :regions, true, :sort_order, NOW())
            """),
            {"code": code, "name": name, "description": description, "gateway": gateway, "regions": regions, "sort_order": sort_order},
        )
    print(f"Migration: seeded {len(_DEFAULT_PAYMENT_METHODS)} default payment methods")


def _backfill_image_storage(db: Session):
    """Classify pre-existing image rows that predate the storage_type column.

    A row is ours when its URL sits under one of our bucket's base URLs; the
    remainder of the URL is the S3 key. Everything else is a pasted external
    link. uploaded_at stays NULL for these rows — the original upload time was
    never recorded and inventing one would be worse than admitting we lack it.
    """
    bases = storage.s3_url_bases()
    if not bases:
        # Without the bucket config every URL would look external, and the
        # storage_type IS NULL guard means that verdict would stick. Leave the
        # rows unclassified and retry on a boot that has the S3 env set.
        print("Migration: skipped image backfill (S3 bucket not configured)")
        return

    for image_table in ("banners", "product_images", "categories"):
        for base in bases:
            prefix = base + "/"
            # :cut is cast explicitly — an untyped bind would make Postgres pick
            # substring(text FROM text), the regex overload, which returns NULL.
            db.execute(
                text(f"""
                    UPDATE {image_table}
                    SET storage_type = 's3', file_name = substring(image_url from cast(:cut as integer))
                    WHERE storage_type IS NULL
                      AND image_url IS NOT NULL
                      AND left(image_url, cast(:plen as integer)) = :prefix
                """),
                {"cut": len(prefix) + 1, "plen": len(prefix), "prefix": prefix},
            )
        db.execute(
            text(f"""
                UPDATE {image_table}
                SET storage_type = 'external'
                WHERE storage_type IS NULL AND image_url IS NOT NULL
            """)
        )
    print("Migration: backfilled image storage_type/file_name")


def _run_migrations(db: Session):
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("categories")]

    if "gender" not in columns:
        db.execute(text("ALTER TABLE categories ADD COLUMN gender VARCHAR(20) NOT NULL DEFAULT 'unisex'"))
        print("Migration: added gender column to categories")

        db.execute(text("""
        UPDATE categories SET gender = 'men'
        WHERE LOWER(TRIM(name)) IN ('men', 'footwear', 'footware', 'kurtas', 'shirts', 'casuals', 'jeans', 'formal wear')
          AND gender IS DISTINCT FROM 'men'
    """))
    db.execute(text("""
        UPDATE categories SET gender = 'women'
        WHERE LOWER(TRIM(name)) IN ('women', 'women footwear', 'western wear', 'top&skirt', 'dress', 'sarees', 'ethnic wear', 'western dress', 'co-ord set')
          AND gender IS DISTINCT FROM 'women'
    """))
    db.execute(text("""
        UPDATE categories SET gender = 'kids'
        WHERE LOWER(TRIM(name)) IN ('kids', 'boys', 'girls')
          AND gender IS DISTINCT FROM 'kids'
    """))
    db.execute(text("""
        UPDATE categories SET gender = 'unisex'
        WHERE TRIM(COALESCE(gender, '')) = ''
    """))
    db.commit()
    print("Migration: category genders synced")

    category_columns = [c["name"] for c in inspector.get_columns("categories")]
    if "parent_id" not in category_columns:
        db.execute(text("ALTER TABLE categories ADD COLUMN parent_id UUID REFERENCES categories(id) ON DELETE CASCADE"))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_categories_parent_id ON categories(parent_id)"))
        print("Migration: added parent_id column to categories")

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
    if "google_id" not in user_columns:
        db.execute(text("ALTER TABLE users ADD COLUMN google_id VARCHAR(255) UNIQUE"))
        print("Migration: added google_id column to users")

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

    # Delivery workflow columns — dispatch OTP, return pickup OTP, evidence,
    # and the lifecycle timestamps the delivery/returns dashboards depend on.
    for _col, _ddl in [
        ("return_evidence", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS return_evidence TEXT"),
        ("return_admin_note", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS return_admin_note TEXT"),
        ("dispatch_otp", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS dispatch_otp VARCHAR(6)"),
        ("dispatch_otp_expires_at", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS dispatch_otp_expires_at TIMESTAMP WITH TIME ZONE"),
        ("return_otp", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS return_otp VARCHAR(6)"),
        ("return_otp_expires_at", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS return_otp_expires_at TIMESTAMP WITH TIME ZONE"),
        ("dispatched_at", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS dispatched_at TIMESTAMP WITH TIME ZONE"),
        ("delivered_at", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP WITH TIME ZONE"),
        ("return_requested_at", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS return_requested_at TIMESTAMP WITH TIME ZONE"),
        ("return_approved_at", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS return_approved_at TIMESTAMP WITH TIME ZONE"),
        ("return_picked_up_at", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS return_picked_up_at TIMESTAMP WITH TIME ZONE"),
    ]:
        if _col not in order_columns:
            db.execute(text(_ddl))
            print(f"Migration: added {_col} column to orders")

    # ShipRocket courier fulfilment columns — populated when a dispatched order
    # is sent to ShipRocket. The AWB is the courier tracking number.
    for _col, _ddl in [
        ("shiprocket_order_id", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS shiprocket_order_id VARCHAR(50)"),
        ("shipment_id", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipment_id VARCHAR(50)"),
        ("awb_code", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS awb_code VARCHAR(100)"),
        ("courier_name", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS courier_name VARCHAR(100)"),
        ("shipment_status", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipment_status VARCHAR(50)"),
        ("tracking_url", "ALTER TABLE orders ADD COLUMN IF NOT EXISTS tracking_url VARCHAR(500)"),
    ]:
        if _col not in order_columns:
            db.execute(text(_ddl))
            print(f"Migration: added {_col} column to orders")

    order_columns = [c["name"] for c in inspector.get_columns("orders")]

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
        # ALTER TYPE ... ADD VALUE errors if the label already exists and, when
        # it does, poisons the surrounding transaction ("current transaction is
        # aborted") so every later migration statement is skipped. Run each in
        # its own committed transaction and roll back on failure.
        db.commit()
        for _val in ("approved", "rejected"):
            try:
                db.execute(text(f"ALTER TYPE reward_status ADD VALUE IF NOT EXISTS '{_val}'"))
                db.commit()
            except Exception:
                db.rollback()

    # pending_payment is the new "waiting for payment" state an order is born in.
    # Unpaid orders used to be created as "placed" immediately, so an abandoned
    # checkout looked like a real order. Same committed-transaction rule applies
    # (ALTER TYPE errors poison the transaction when the label already exists).
    db.commit()
    try:
        db.execute(text("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'pending_payment'"))
        db.commit()
        print("Migration: added pending_payment to order_status enum")
    except Exception:
        db.rollback()

    # Rewrite legacy unpaid orders born as "placed" into awaiting-payment so the
    # 30-minute expiry sweep can cancel them and release the reserved stock. COD
    # orders are excluded — they are legitimately in flight with payment at the
    # doorstep, so their status stays "placed".
    db.commit()
    try:
        migrated = db.execute(text("""
            UPDATE orders o
            SET order_status = 'pending_payment'
            WHERE o.order_status = 'placed'
              AND o.payment_status = 'pending'
              AND NOT EXISTS (
                  SELECT 1 FROM payments p
                  WHERE p.order_id = o.id
                    AND (p.gateway = 'cod' OR p.payment_method = 'cod')
              )
        """))
        db.commit()
        print(f"Migration: rewrote {migrated.rowcount} unpaid placed orders as pending_payment")
    except Exception:
        db.rollback()

    product_columns = [c["name"] for c in inspector.get_columns("products")] if "products" in tables else []
    if "is_replaceable" not in product_columns:
        db.execute(text("ALTER TABLE products ADD COLUMN is_replaceable BOOLEAN DEFAULT FALSE"))
        db.execute(text("ALTER TABLE products ADD COLUMN is_returnable BOOLEAN DEFAULT FALSE"))
        print("Migration: added is_replaceable and is_returnable columns to products")

    # GST is fixed (not per product): CGST+SGST intra-state, IGST inter-state,
    # decided at checkout from the customer's state. Drop any per-product GST
    # columns and store the split amounts on the order instead.
    db.execute(text("ALTER TABLE products DROP COLUMN IF EXISTS gst_percentage"))
    db.execute(text("ALTER TABLE products DROP COLUMN IF EXISTS cgst_percentage"))
    db.execute(text("ALTER TABLE products DROP COLUMN IF EXISTS sgst_percentage"))
    db.execute(text("ALTER TABLE products DROP COLUMN IF EXISTS igst_percentage"))
    db.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS cgst_amount FLOAT DEFAULT 0.0"))
    db.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS sgst_amount FLOAT DEFAULT 0.0"))
    db.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS igst_amount FLOAT DEFAULT 0.0"))
    db.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_fee FLOAT DEFAULT 0.0"))
    db.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_state VARCHAR(100)"))

    if "coupons" not in tables:
        db.execute(text("""
            CREATE TABLE coupons (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                code VARCHAR(50) UNIQUE NOT NULL,
                type VARCHAR(20) NOT NULL DEFAULT 'percentage',
                value FLOAT NOT NULL,
                min_order_amount FLOAT,
                max_discount FLOAT,
                expiry_date VARCHAR(50),
                usage_limit INTEGER DEFAULT 100,
                used_count INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_coupons_code ON coupons(code)"))
        print("Migration: created coupons table")

    db.execute(text("ALTER TABLE payments ADD COLUMN IF NOT EXISTS gateway_order_id VARCHAR(255)"))

    # Image provenance: where each image lives, so S3-hosted ones can be removed
    # from the bucket when deleted while pasted external URLs are only unlinked.
    for image_table in ("banners", "product_images", "categories"):
        db.execute(text(f"ALTER TABLE {image_table} ADD COLUMN IF NOT EXISTS storage_type VARCHAR(16)"))
        db.execute(text(f"ALTER TABLE {image_table} ADD COLUMN IF NOT EXISTS file_name VARCHAR(255)"))
        db.execute(text(f"ALTER TABLE {image_table} ADD COLUMN IF NOT EXISTS uploaded_at TIMESTAMP WITH TIME ZONE"))
    db.commit()
    _backfill_image_storage(db)

    # Payment methods are presented to the buyer instead of the gateway name.
    # country decides which of them a buyer is offered; existing rows predate
    # any non-Indian customer, so they are India.
    db.execute(text("ALTER TABLE addresses ADD COLUMN IF NOT EXISTS country VARCHAR(2) DEFAULT 'IN'"))
    db.execute(text("UPDATE addresses SET country = 'IN' WHERE country IS NULL"))
    # Cashfree replaced Razorpay as the gateway: existing rows created under the
    # old default are rewritten so the Admin app and the checkout agree on which
    # gateway charges the order.
    db.execute(text("UPDATE payment_methods SET gateway = 'cashfree' WHERE gateway IS NOT DISTINCT FROM 'razorpay'"))
    db.commit()
    _seed_payment_methods(db)

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

# CORS_ORIGINS may be a single origin or a comma-separated list (e.g. the
# admin and shop CloudFront URLs). Browsers reject credentialed requests when
# the allowed origin is "*", so when a wildcard is configured we disable
# credentials and echo any origin instead of sending a broken combination.
_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
_allow_all = "*" in _origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allow_all else _origins,
    allow_credentials=not _allow_all,
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
app.include_router(delivery.router)
app.include_router(payment_methods.router)
app.include_router(uploads.router)
app.include_router(contact.router)
app.include_router(fulfillment.router)


@app.get("/")
def root():
    return {"message": "Garment E-commerce Platform API", "version": settings.APP_VERSION, "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "healthy"}
