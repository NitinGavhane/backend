from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.cart import CartAddRequest, CartUpdateRequest, CartResponse
from app.services import cart_service

router = APIRouter(prefix="/api/v1/cart", tags=["Cart"])


@router.get("", response_model=CartResponse)
def get_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return cart_service.get_cart(str(user.id), db)


@router.post("/add", response_model=CartResponse)
def add_to_cart(req: CartAddRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return cart_service.add_to_cart(str(user.id), req, db)


@router.put("/update", response_model=CartResponse)
def update_cart(req: CartUpdateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return cart_service.update_cart(str(user.id), req, db)


@router.delete("/remove/{cart_item_id}", response_model=CartResponse)
def remove_from_cart(cart_item_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return cart_service.remove_from_cart(str(user.id), cart_item_id, db)
