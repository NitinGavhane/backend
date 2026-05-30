from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.cart import AddToCartRequest, UpdateCartItemRequest
from app.services import cart_service

router = APIRouter(prefix="/api/cart", tags=["Cart"])


@router.get("")
def get_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = cart_service.get_cart(db, current_user.id)
    return {"items": items}


@router.post("")
def add_to_cart(
    req: AddToCartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return cart_service.add_to_cart(
        db, current_user.id, req.productId, req.quantity, req.selectedSize, req.selectedColor
    )


@router.put("/{item_id}")
def update_cart_item(
    item_id: str,
    req: UpdateCartItemRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return cart_service.update_cart_item(db, current_user.id, item_id, req.quantity)


@router.delete("/{item_id}")
def remove_from_cart(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return cart_service.remove_from_cart(db, current_user.id, item_id)
