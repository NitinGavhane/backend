from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services import user_service

router = APIRouter(prefix="/api/wishlist", tags=["Wishlist"])


@router.get("")
def get_wishlist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    products = user_service.get_wishlist(db, current_user.id)
    return {"products": products, "count": len(products)}


@router.post("/{product_id}")
def add_to_wishlist(
    product_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return user_service.add_to_wishlist(db, current_user.id, product_id)


@router.delete("/{product_id}")
def remove_from_wishlist(
    product_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return user_service.remove_from_wishlist(db, current_user.id, product_id)
