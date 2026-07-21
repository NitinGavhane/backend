import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core import storage
from app.core.config import settings
from app.core.database import Base, get_db, engine
from app.core.deps import get_current_admin
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.models.order import Order
from app.models.payment_method import PaymentMethod
from app.models.product import Product
from app.models.user import User
from app.models.coupon import Coupon
from app.schemas.admin import AdminDashboardStats, AdminUserResponse
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.banner import BannerCreate, BannerResponse, BannerUpdate
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.schemas.coupon import CouponCreate, CouponResponse, CouponUpdate
from app.schemas.delivery import DeliverySettingsResponse, DeliverySettingsUpdate
from app.schemas.order import OrderResponse
from app.schemas.payment_method import AdminPaymentMethodResponse, PaymentMethodCreate, PaymentMethodUpdate
from app.schemas.product import AdminProductResponse, ProductCreate, ProductUpdate
from app.schemas.referral import (
    AdminReferralPurchaseResponse,
    ApproveRewardRequest,
    ReferralHistoryResponse,
    ReferralProductReport,
    ReferralUserReport,
)
from app.services import delivery_service, order_service, product_service, referral_service
from app.models.referral import ReferralEarning
from app.models.category import Category
from app.models.banner import Banner

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


@router.post("/login", response_model=TokenResponse)
def admin_login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    access_token = create_access_token({"sub": str(user.id), "role": user.role})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@router.get("/dashboard", response_model=AdminDashboardStats)
def get_dashboard(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    total_users = db.query(User).count()
    total_products = db.query(Product).count()
    total_orders = db.query(Order).count()
    total_revenue = db.query(Order).filter(Order.payment_status == "paid").with_entities(Order.final_amount).all()
    total_revenue_sum = sum(r[0] for r in total_revenue if r[0])
    pending_orders = db.query(Order).filter(Order.order_status == "placed").count()
    return {
        "total_users": total_users,
        "total_products": total_products,
        "total_orders": total_orders,
        "total_revenue": round(total_revenue_sum, 2),
        "pending_orders": pending_orders,
    }


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "id": str(u.id),
            "full_name": u.full_name,
            "email": u.email,
            "phone": u.phone,
            "avatar_url": u.avatar_url if hasattr(u, "avatar_url") else None,
            "role": u.role,
            "referral_code": u.referral_code,
            "wallet_balance": u.wallet_balance,
            "is_verified": u.is_verified,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.get("/orders", response_model=list[OrderResponse])
def list_all_orders(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    orders = db.query(Order).order_by(Order.created_at.desc()).all()
    return [order_service.format_order(o) for o in orders]


@router.put("/orders/{order_id}/status", response_model=OrderResponse)
def admin_update_order_status(order_id: str, req: dict, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return order_service.update_order_status(order_id, req.get("status", ""), db)


@router.get("/referrals", response_model=list[ReferralHistoryResponse])
def list_all_referrals(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    earnings = db.query(ReferralEarning).order_by(ReferralEarning.created_at.desc()).all()
    return [
        {
            "id": str(e.id),
            "referred_user_name": "User",
            "order_id": str(e.order_id),
            "commission_amount": e.reward_amount,
            "status": e.status,
            "created_at": e.created_at,
        }
        for e in earnings
    ]


@router.get("/referral-purchases", response_model=list[AdminReferralPurchaseResponse])
def list_referral_purchases(
    status: str | None = None,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return referral_service.get_admin_referral_purchases(db, status)


@router.put("/referral-purchases/{earning_id}/approve")
def approve_referral_reward(
    earning_id: str,
    req: ApproveRewardRequest,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return referral_service.approve_referral_reward(earning_id, req.reward_percentage, req.reward_amount, db)


@router.put("/referral-purchases/{earning_id}/reject")
def reject_referral_reward(
    earning_id: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return referral_service.reject_referral_reward(earning_id, db)


@router.get("/referral-reports/product", response_model=list[ReferralProductReport])
def product_referral_report(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return referral_service.get_product_referral_report(db)


@router.get("/referral-reports/user", response_model=list[ReferralUserReport])
def user_referral_report(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return referral_service.get_user_referral_report(db)


@router.get("/products", response_model=list[AdminProductResponse])
def list_admin_products(gender: str | None = None, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return product_service.list_admin_products(db, gender)


@router.get("/products/{product_id}", response_model=AdminProductResponse)
def get_admin_product(product_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return product_service.get_admin_product(product_id, db)


@router.post("/products", response_model=AdminProductResponse)
def create_product(req: ProductCreate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return product_service.create_product(req, db)


@router.put("/products/{product_id}", response_model=AdminProductResponse)
def update_product(product_id: str, req: ProductUpdate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return product_service.update_product(product_id, req, db)


@router.delete("/products/{product_id}")
def delete_product(product_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return product_service.delete_product(product_id, db)


@router.get("/delivery-settings", response_model=DeliverySettingsResponse)
def get_delivery_settings(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return delivery_service.get_settings(db)


@router.put("/delivery-settings", response_model=DeliverySettingsResponse)
def update_delivery_settings(req: DeliverySettingsUpdate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return delivery_service.update_settings(req, db)


@router.get("/coupons", response_model=list[CouponResponse])
def list_coupons(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    coupons = db.query(Coupon).order_by(Coupon.created_at.desc()).all()
    return coupons


@router.get("/coupons/{coupon_id}", response_model=CouponResponse)
def get_coupon(coupon_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found")
    return coupon


@router.post("/coupons", response_model=CouponResponse)
def create_coupon(req: CouponCreate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    existing = db.query(Coupon).filter(Coupon.code == req.code.upper()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Coupon code already exists")
    coupon = Coupon(
        code=req.code.upper(),
        type=req.type,
        value=req.value,
        min_order_amount=req.min_order_amount,
        max_discount=req.max_discount,
        expiry_date=req.expiry_date,
        usage_limit=req.usage_limit,
        is_active=req.is_active,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.put("/coupons/{coupon_id}", response_model=CouponResponse)
def update_coupon(coupon_id: str, req: CouponUpdate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found")
    update_data = req.model_dump(exclude_unset=True)
    if "code" in update_data:
        update_data["code"] = update_data["code"].upper()
    for key, value in update_data.items():
        setattr(coupon, key, value)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.delete("/coupons/{coupon_id}")
def delete_coupon(coupon_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found")
    db.delete(coupon)
    db.commit()
    return {"message": "Coupon deleted successfully"}


def _category_dict(c: Category) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "slug": c.slug,
        "description": c.description,
        "image_url": c.image_url,
        "storage_type": c.storage_type,
        "file_name": c.file_name,
        "uploaded_at": c.uploaded_at,
        "parent_id": str(c.parent_id) if c.parent_id else None,
        "gender": c.gender,
        "is_active": c.is_active,
        "created_at": c.created_at,
    }


@router.get("/categories/{category_id}", response_model=CategoryResponse)
def get_admin_category(category_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return _category_dict(category)


@router.get("/categories", response_model=list[CategoryResponse])
def list_admin_categories(gender: str | None = None, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    query = db.query(Category).filter(Category.is_active == True)
    if gender:
        query = query.filter(Category.gender == gender)
    categories = query.order_by(Category.created_at.desc()).all()
    return [_category_dict(c) for c in categories]


_SPECIFIC_GENDERS = {"men", "women", "kids"}


def _resolve_category_gender(name: str | None, requested_gender: str | None, parent_uuid: uuid.UUID | None, db: Session) -> str:
    """Resolve the effective gender for a category.

    Priority: an explicitly chosen real gender (men/women/kids) > the parent's
    gender (so a subcategory under "Kids" becomes "kids") > the category's own
    name when it is a main gender category > "unisex".
    """
    if requested_gender and requested_gender.lower() in _SPECIFIC_GENDERS:
        return requested_gender.lower()
    if parent_uuid:
        parent = db.query(Category).filter(Category.id == parent_uuid).first()
        if parent:
            if parent.gender and parent.gender.lower() in _SPECIFIC_GENDERS:
                return parent.gender.lower()
            if parent.name and parent.name.strip().lower() in _SPECIFIC_GENDERS:
                return parent.name.strip().lower()
    if name and name.strip().lower() in _SPECIFIC_GENDERS:
        return name.strip().lower()
    return (requested_gender or "unisex").lower()


@router.post("/categories", response_model=CategoryResponse)
def create_category(req: CategoryCreate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    parent_uuid = uuid.UUID(req.parent_id) if req.parent_id else None
    resolved_gender = _resolve_category_gender(req.name, req.gender, parent_uuid, db)
    category = Category(
        name=req.name, slug=req.slug,
        description=req.description, image_url=req.image_url,
        parent_id=parent_uuid, gender=resolved_gender,
        **storage.image_metadata(req.image_url),
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return _category_dict(category)


@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(category_id: str, req: CategoryUpdate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    update_data = req.model_dump(exclude_unset=True)
    if "parent_id" in update_data:
        update_data["parent_id"] = uuid.UUID(update_data["parent_id"]) if update_data["parent_id"] else None
    # Only re-derive metadata when the image actually changes, so an unrelated
    # edit (name, gender) doesn't reset uploaded_at.
    replaced_image = None
    if "image_url" in update_data and update_data["image_url"] != category.image_url:
        replaced_image = category.image_url
        update_data.update(storage.image_metadata(update_data["image_url"]))
    for key, value in update_data.items():
        setattr(category, key, value)
    # Re-resolve gender whenever the inputs that determine it may have changed,
    # so a category moved under a gender parent inherits the right gender.
    if {"gender", "parent_id", "name"} & set(update_data.keys()):
        category.gender = _resolve_category_gender(
            category.name, update_data.get("gender", category.gender), category.parent_id, db
        )
    db.commit()
    db.refresh(category)
    # Drop the old object only after the new URL is safely committed.
    storage.delete_image_from_s3(replaced_image)
    return _category_dict(category)


@router.delete("/categories/{category_id}")
def delete_category(category_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    children = db.query(Category).filter(Category.parent_id == category_id).all()
    # Children are deleted alongside the parent, so their images go too.
    image_urls = [c.image_url for c in [category, *children]]
    for child in children:
        db.delete(child)
    db.delete(category)
    db.commit()
    storage.delete_images_from_s3(image_urls)
    return {"message": "Category deleted successfully"}


# ── Banners (sliding hero banners) ───────────────────────────────────────────

def _banner_dict(b: Banner) -> dict:
    return {
        "id": str(b.id),
        "title": b.title,
        "subtitle": b.subtitle,
        "image_url": b.image_url,
        "storage_type": b.storage_type,
        "file_name": b.file_name,
        "uploaded_at": b.uploaded_at,
        "link_url": b.link_url,
        "link_text": b.link_text,
        "section": b.section,
        "sort_order": b.sort_order,
        "is_active": b.is_active,
    }


@router.get("/banners", response_model=list[BannerResponse])
def list_admin_banners(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    banners = db.query(Banner).order_by(Banner.sort_order.asc(), Banner.created_at.desc()).all()
    return [_banner_dict(b) for b in banners]


@router.get("/banners/{banner_id}", response_model=BannerResponse)
def get_admin_banner(banner_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    banner = db.query(Banner).filter(Banner.id == banner_id).first()
    if not banner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")
    return _banner_dict(banner)


@router.post("/banners", response_model=BannerResponse)
def create_banner(req: BannerCreate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    banner = Banner(**req.model_dump(), **storage.image_metadata(req.image_url))
    db.add(banner)
    db.commit()
    db.refresh(banner)
    return _banner_dict(banner)


@router.put("/banners/{banner_id}", response_model=BannerResponse)
def update_banner(banner_id: str, req: BannerUpdate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    banner = db.query(Banner).filter(Banner.id == banner_id).first()
    if not banner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")
    update_data = req.model_dump(exclude_unset=True)
    # Only re-derive metadata when the image actually changes, so an unrelated
    # edit (title, sort order) doesn't reset uploaded_at.
    replaced_image = None
    if "image_url" in update_data and update_data["image_url"] != banner.image_url:
        replaced_image = banner.image_url
        update_data.update(storage.image_metadata(update_data["image_url"]))
    for key, value in update_data.items():
        setattr(banner, key, value)
    db.commit()
    db.refresh(banner)
    # Drop the old object only after the new URL is safely committed.
    storage.delete_image_from_s3(replaced_image)
    return _banner_dict(banner)


@router.delete("/banners/{banner_id}")
def delete_banner(banner_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    banner = db.query(Banner).filter(Banner.id == banner_id).first()
    if not banner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")
    image_url = banner.image_url
    db.delete(banner)
    db.commit()
    storage.delete_image_from_s3(image_url)
    return {"message": "Banner deleted successfully"}


# ── Payment methods ──────────────────────────────────────────────────────────
#
# What the buyer picks at checkout. The gateway behind a method is configuration
# here, never something the storefront names.

def _payment_method_dict(m: PaymentMethod) -> dict:
    return {
        "id": str(m.id),
        "code": m.code,
        "name": m.name,
        "description": m.description,
        "icon_url": m.icon_url,
        "gateway": m.gateway,
        "regions": m.regions,
        "is_active": m.is_active,
        "sort_order": m.sort_order,
    }


def _normalised_method_fields(data: dict) -> dict:
    """Codes and regions are matched case-insensitively elsewhere, so store them
    in one canonical case rather than relying on every caller to agree."""
    if "code" in data and data["code"]:
        data["code"] = data["code"].strip().lower()
    if "regions" in data and data["regions"]:
        regions = data["regions"].strip()
        data["regions"] = regions if regions == "*" else ",".join(
            r.strip().upper() for r in regions.split(",") if r.strip()
        )
    return data


@router.get("/payment-methods", response_model=list[AdminPaymentMethodResponse])
def list_admin_payment_methods(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    methods = db.query(PaymentMethod).order_by(PaymentMethod.sort_order.asc(), PaymentMethod.name.asc()).all()
    return [_payment_method_dict(m) for m in methods]


@router.get("/payment-methods/{method_id}", response_model=AdminPaymentMethodResponse)
def get_admin_payment_method(method_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    method = db.query(PaymentMethod).filter(PaymentMethod.id == method_id).first()
    if not method:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment method not found")
    return _payment_method_dict(method)


@router.post("/payment-methods", response_model=AdminPaymentMethodResponse)
def create_payment_method(req: PaymentMethodCreate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    data = _normalised_method_fields(req.model_dump())
    if db.query(PaymentMethod).filter(PaymentMethod.code == data["code"]).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A payment method with code '{data['code']}' already exists",
        )
    method = PaymentMethod(**data)
    db.add(method)
    db.commit()
    db.refresh(method)
    return _payment_method_dict(method)


@router.put("/payment-methods/{method_id}", response_model=AdminPaymentMethodResponse)
def update_payment_method(method_id: str, req: PaymentMethodUpdate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    method = db.query(PaymentMethod).filter(PaymentMethod.id == method_id).first()
    if not method:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment method not found")
    data = _normalised_method_fields(req.model_dump(exclude_unset=True))
    if "code" in data:
        clash = db.query(PaymentMethod).filter(PaymentMethod.code == data["code"], PaymentMethod.id != method.id).first()
        if clash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A payment method with code '{data['code']}' already exists",
            )
    for key, value in data.items():
        setattr(method, key, value)
    db.commit()
    db.refresh(method)
    return _payment_method_dict(method)


@router.delete("/payment-methods/{method_id}")
def delete_payment_method(method_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    method = db.query(PaymentMethod).filter(PaymentMethod.id == method_id).first()
    if not method:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment method not found")
    # Payment rows record the method as free text, so deleting one leaves past
    # payments readable. Deactivating is still the gentler option for a method
    # in use, which is why is_active exists.
    db.delete(method)
    db.commit()
    return {"message": "Payment method deleted successfully"}


@router.post("/migrate")
def run_migration(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    from app.models.address import Address
    from app.models.banner import Banner
    from app.models.blog import BlogPost
    from app.models.review import Review
    from app.models.wishlist import WishlistItem
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    user_columns = [c["name"] for c in inspector.get_columns("users")] if "users" in tables else []
    if "avatar_url" not in user_columns:
        db.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500)"))
    order_columns = [c["name"] for c in inspector.get_columns("orders")] if "orders" in tables else []
    if "return_reason" not in order_columns:
        db.execute(text("ALTER TABLE orders ADD COLUMN return_reason TEXT"))
        db.execute(text("ALTER TABLE orders ADD COLUMN return_status VARCHAR(20)"))
    # Product flags required by the Product model. These are added idempotently
    # with IF NOT EXISTS because the lifespan migration that normally adds them
    # does not run on serverless (Vercel) cold starts — a missing column here
    # makes every product query fail with a 500. See _run_migrations in main.py.
    db.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS is_replaceable BOOLEAN DEFAULT FALSE"))
    db.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS is_returnable BOOLEAN DEFAULT FALSE"))
    db.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS gender VARCHAR(20) DEFAULT 'unisex'"))
    # GST is fixed (not per product): drop any per-product GST columns and store
    # the CGST/SGST/IGST split on the order (set at checkout by place of supply).
    db.execute(text("ALTER TABLE products DROP COLUMN IF EXISTS gst_percentage"))
    db.execute(text("ALTER TABLE products DROP COLUMN IF EXISTS cgst_percentage"))
    db.execute(text("ALTER TABLE products DROP COLUMN IF EXISTS sgst_percentage"))
    db.execute(text("ALTER TABLE products DROP COLUMN IF EXISTS igst_percentage"))
    db.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS cgst_amount FLOAT DEFAULT 0.0"))
    db.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS sgst_amount FLOAT DEFAULT 0.0"))
    db.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS igst_amount FLOAT DEFAULT 0.0"))
    db.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_fee FLOAT DEFAULT 0.0"))
    db.execute(text("ALTER TABLE categories ADD COLUMN IF NOT EXISTS gender VARCHAR(20) DEFAULT 'unisex'"))
    db.execute(text("ALTER TABLE categories ADD COLUMN IF NOT EXISTS parent_id UUID REFERENCES categories(id) ON DELETE CASCADE"))
    db.commit()
    product_columns = [c["name"] for c in inspect(engine).get_columns("products")] if "products" in tables else []
    return {"message": "Migration completed successfully", "tables": tables, "user_columns": user_columns, "order_columns": order_columns, "product_columns": product_columns}


@router.get("/debug-db")
def debug_db(admin: User = Depends(get_current_admin)):
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    result = {"tables": tables}
    for t in tables:
        cols = [c["name"] for c in inspector.get_columns(t)]
        result[t] = cols
    return result
