import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base, get_db, engine
from app.core.deps import get_current_admin
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.models.coupon import Coupon
from app.schemas.admin import AdminDashboardStats, AdminUserResponse
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.schemas.coupon import CouponCreate, CouponResponse, CouponUpdate
from app.schemas.order import OrderResponse
from app.schemas.product import AdminProductResponse, ProductCreate, ProductUpdate
from app.schemas.referral import (
    AdminReferralPurchaseResponse,
    ApproveRewardRequest,
    ReferralHistoryResponse,
    ReferralProductReport,
    ReferralUserReport,
)
from app.services import order_service, product_service, referral_service
from app.models.referral import ReferralEarning
from app.models.category import Category

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


@router.get("/categories/{category_id}", response_model=CategoryResponse)
def get_admin_category(category_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return {
        "id": str(category.id),
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
        "image_url": category.image_url,
        "parent_id": str(category.parent_id) if category.parent_id else None,
        "gender": category.gender,
        "is_active": category.is_active,
        "created_at": category.created_at,
    }


@router.get("/categories", response_model=list[CategoryResponse])
def list_admin_categories(gender: str | None = None, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    query = db.query(Category).filter(Category.is_active == True)
    if gender:
        query = query.filter(Category.gender == gender)
    categories = query.order_by(Category.created_at.desc()).all()
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "slug": c.slug,
            "description": c.description,
            "image_url": c.image_url,
            "parent_id": str(c.parent_id) if c.parent_id else None,
            "gender": c.gender,
            "is_active": c.is_active,
            "created_at": c.created_at,
        }
        for c in categories
    ]


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
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return {
        "id": str(category.id),
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
        "image_url": category.image_url,
        "parent_id": str(category.parent_id) if category.parent_id else None,
        "gender": category.gender,
        "is_active": category.is_active,
        "created_at": category.created_at,
    }


@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(category_id: str, req: CategoryUpdate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    update_data = req.model_dump(exclude_unset=True)
    if "parent_id" in update_data:
        update_data["parent_id"] = uuid.UUID(update_data["parent_id"]) if update_data["parent_id"] else None
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
    return {
        "id": str(category.id),
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
        "image_url": category.image_url,
        "parent_id": str(category.parent_id) if category.parent_id else None,
        "gender": category.gender,
        "is_active": category.is_active,
        "created_at": category.created_at,
    }


@router.delete("/categories/{category_id}")
def delete_category(category_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    children = db.query(Category).filter(Category.parent_id == category_id).all()
    for child in children:
        db.delete(child)
    db.delete(category)
    db.commit()
    return {"message": "Category deleted successfully"}


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
