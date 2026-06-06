from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.cart import CartItem
from app.models.product import Product, ProductImage, ProductVariant
from app.schemas.cart import CartAddRequest, CartUpdateRequest


def get_cart(user_id: str, db: Session) -> dict:
    items = db.query(CartItem).options(joinedload(CartItem.product), joinedload(CartItem.variant)).filter(CartItem.user_id == user_id).all()
    total = 0.0
    item_list = []
    for item in items:
        price = item.product.discount_price or item.product.price
        subtotal = price * item.quantity
        total += subtotal
        primary_image = db.query(ProductImage).filter(ProductImage.product_id == item.product_id, ProductImage.is_primary == True).first()
        image_url = primary_image.image_url if primary_image else None
        variant_info = None
        if item.variant:
            parts = []
            if item.variant.size:
                parts.append(f"Size: {item.variant.size}")
            if item.variant.color:
                parts.append(f"Color: {item.variant.color}")
            variant_info = ", ".join(parts)
        item_list.append({
            "id": str(item.id),
            "product_id": str(item.product_id),
            "product_title": item.product.title,
            "variant_id": str(item.variant_id) if item.variant_id else None,
            "variant_info": variant_info,
            "quantity": item.quantity,
            "price": price,
            "image_url": image_url,
        })
    return {"items": item_list, "total": round(total, 2)}


def add_to_cart(user_id: str, req: CartAddRequest, db: Session) -> dict:
    product = db.query(Product).filter(Product.id == req.product_id, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if req.variant_id:
        variant = db.query(ProductVariant).filter(ProductVariant.id == req.variant_id, ProductVariant.product_id == req.product_id).first()
        if not variant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
    existing = db.query(CartItem).filter(CartItem.user_id == user_id, CartItem.product_id == req.product_id, CartItem.variant_id == req.variant_id).first()
    if existing:
        existing.quantity += req.quantity
    else:
        item = CartItem(user_id=user_id, product_id=req.product_id, variant_id=req.variant_id, quantity=req.quantity)
        db.add(item)
    db.commit()
    return get_cart(user_id, db)


def update_cart(user_id: str, req: CartUpdateRequest, db: Session) -> dict:
    item = db.query(CartItem).filter(CartItem.id == req.cart_item_id, CartItem.user_id == user_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")
    if req.quantity <= 0:
        db.delete(item)
    else:
        item.quantity = req.quantity
    db.commit()
    return get_cart(user_id, db)


def remove_from_cart(user_id: str, cart_item_id: str, db: Session) -> dict:
    item = db.query(CartItem).filter(CartItem.id == cart_item_id, CartItem.user_id == user_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")
    db.delete(item)
    db.commit()
    return get_cart(user_id, db)
