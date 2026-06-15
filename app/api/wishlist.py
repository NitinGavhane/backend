from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.wishlist import WishlistAddRequest, WishlistItemResponse
from app.services import wishlist_service

router = APIRouter(prefix="/api/v1/wishlist", tags=["Wishlist"])


@router.get("", response_model=list[WishlistItemResponse])
def get_wishlist(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return wishlist_service.get_wishlist(str(user.id), db)


@router.post("/add")
def add_to_wishlist(req: WishlistAddRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return wishlist_service.add_to_wishlist(str(user.id), req.product_id, db)


@router.delete("/remove/{product_id}")
def remove_from_wishlist(product_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return wishlist_service.remove_from_wishlist(str(user.id), product_id, db)
