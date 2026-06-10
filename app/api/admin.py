from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.core.security import create_access_token, create_refresh_token, verify_password
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.schemas.admin import AdminDashboardStats, AdminUserResponse
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.schemas.order import OrderResponse
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.schemas.referral import ReferralHistoryResponse
from app.services import order_service, product_service
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


@router.get("/referrals", response_model=list[ReferralHistoryResponse])
def list_all_referrals(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    earnings = db.query(ReferralEarning).order_by(ReferralEarning.created_at.desc()).all()
    return [
        {
            "id": str(e.id),
            "referred_user_name": "User",
            "order_id": str(e.order_id),
            "commission_amount": e.commission_amount,
            "status": e.status,
            "created_at": e.created_at,
        }
        for e in earnings
    ]


@router.post("/products", response_model=ProductResponse)
def create_product(req: ProductCreate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return product_service.create_product(req, db)


@router.put("/products/{product_id}", response_model=ProductResponse)
def update_product(product_id: str, req: ProductUpdate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return product_service.update_product(product_id, req, db)


@router.delete("/products/{product_id}")
def delete_product(product_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return product_service.delete_product(product_id, db)


@router.post("/categories", response_model=CategoryResponse)
def create_category(req: CategoryCreate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    category = Category(name=req.name, slug=req.slug, description=req.description, image_url=req.image_url, gender=req.gender)
    db.add(category)
    db.commit()
    db.refresh(category)
    return {
        "id": str(category.id),
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
        "image_url": category.image_url,
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
    for key, value in update_data.items():
        setattr(category, key, value)
    db.commit()
    db.refresh(category)
    return {
        "id": str(category.id),
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
        "image_url": category.image_url,
        "gender": category.gender,
        "is_active": category.is_active,
        "created_at": category.created_at,
    }


@router.delete("/categories/{category_id}")
def delete_category(category_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    db.delete(category)
    db.commit()
    return {"message": "Category deleted successfully"}
