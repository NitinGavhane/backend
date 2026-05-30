import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.cart import CartItem
from app.models.product import Product


def get_cart(db: Session, user_id: str) -> list:
    items = db.query(CartItem).filter(CartItem.user_id == user_id).all()
    return [item.to_dict() for item in items]


def add_to_cart(db: Session, user_id: str, product_id: str, quantity: int, selected_size: str, selected_color: str) -> dict:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if product.stock < quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient stock")

    existing = db.query(CartItem).filter(
        CartItem.user_id == user_id,
        CartItem.product_id == product_id,
        CartItem.selected_size == selected_size,
        CartItem.selected_color == selected_color,
    ).first()

    if existing:
        existing.quantity += quantity
        db.commit()
        db.refresh(existing)
        return existing.to_dict()

    item = CartItem(
        id=str(uuid.uuid4()),
        user_id=user_id,
        product_id=product_id,
        quantity=quantity,
        selected_size=selected_size,
        selected_color=selected_color,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item.to_dict()


def update_cart_item(db: Session, user_id: str, item_id: str, quantity: int) -> dict:
    item = db.query(CartItem).filter(
        CartItem.id == item_id, CartItem.user_id == user_id
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")

    if quantity <= 0:
        db.delete(item)
        db.commit()
        return {"deleted": True}

    product = db.query(Product).filter(Product.id == item.product_id).first()
    if product and product.stock < quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient stock")

    item.quantity = quantity
    db.commit()
    db.refresh(item)
    return item.to_dict()


def remove_from_cart(db: Session, user_id: str, item_id: str) -> dict:
    item = db.query(CartItem).filter(
        CartItem.id == item_id, CartItem.user_id == user_id
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")

    db.delete(item)
    db.commit()
    return {"deleted": True}


def clear_cart(db: Session, user_id: str) -> dict:
    db.query(CartItem).filter(CartItem.user_id == user_id).delete()
    db.commit()
    return {"cleared": True}
