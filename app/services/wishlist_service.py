import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.product import Product, ProductImage
from app.models.wishlist import WishlistItem


def get_wishlist(user_id: str, db: Session):
    items = db.query(WishlistItem).filter(WishlistItem.user_id == user_id).order_by(WishlistItem.created_at.desc()).all()
    result = []
    for item in items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        primary_image = None
        if product:
            img = db.query(ProductImage).filter(ProductImage.product_id == product.id, ProductImage.is_primary == True).first()
            if not img:
                img = db.query(ProductImage).filter(ProductImage.product_id == product.id).first()
            primary_image = img.image_url if img else None
        result.append({
            "id": str(item.id),
            "product_id": str(item.product_id),
            "product_title": product.title if product else None,
            "price": (product.discount_price or product.price) if product else None,
            "image_url": primary_image,
            "created_at": item.created_at,
        })
    return result


def add_to_wishlist(user_id: str, product_id: str, db: Session):
    pid = _parse_uuid(product_id, "product_id")
    product = db.query(Product).filter(Product.id == pid).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    existing = db.query(WishlistItem).filter(WishlistItem.user_id == user_id, WishlistItem.product_id == pid).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product already in wishlist")
    item = WishlistItem(user_id=uuid.UUID(user_id), product_id=pid)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"message": "Added to wishlist", "id": str(item.id)}


def remove_from_wishlist(user_id: str, product_id: str, db: Session):
    pid = _parse_uuid(product_id, "product_id")
    item = db.query(WishlistItem).filter(WishlistItem.user_id == user_id, WishlistItem.product_id == pid).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist item not found")
    db.delete(item)
    db.commit()
    return {"message": "Removed from wishlist"}


def _parse_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid {field}: must be a valid UUID")
