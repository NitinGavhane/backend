from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import User
from app.models.wishlist import wishlist_table
from app.models.product import Product


def get_profile(db: Session, user_id: str) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user.to_dict()


def update_profile(db: Session, user_id: str, full_name: Optional[str] = None, phone: Optional[str] = None, avatar_url: Optional[str] = None) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if full_name is not None:
        user.full_name = full_name
    if phone is not None:
        user.phone = phone
    if avatar_url is not None:
        user.avatar_url = avatar_url

    db.commit()
    db.refresh(user)
    return user.to_dict()


def get_wishlist(db: Session, user_id: str) -> list:
    result = db.execute(
        wishlist_table.select().where(wishlist_table.c.user_id == user_id)
    ).fetchall()
    product_ids = [row.product_id for row in result]
    products = db.query(Product).filter(Product.id.in_(product_ids)).all()
    return [p.to_dict() for p in products]


def add_to_wishlist(db: Session, user_id: str, product_id: str) -> dict:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    existing = db.execute(
        wishlist_table.select().where(
            wishlist_table.c.user_id == user_id,
            wishlist_table.c.product_id == product_id,
        )
    ).first()

    if not existing:
        db.execute(wishlist_table.insert().values(user_id=user_id, product_id=product_id))
        db.commit()

    return {"added": True}


def remove_from_wishlist(db: Session, user_id: str, product_id: str) -> dict:
    db.execute(
        wishlist_table.delete().where(
            wishlist_table.c.user_id == user_id,
            wishlist_table.c.product_id == product_id,
        )
    )
    db.commit()
    return {"removed": True}
