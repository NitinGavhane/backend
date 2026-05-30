import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.review import Review
from app.models.product import Product
from app.models.user import User


def get_product_reviews(db: Session, product_id: str) -> list:
    reviews = db.query(Review).filter(Review.product_id == product_id).order_by(
        Review.created_at.desc()
    ).all()
    return [r.to_dict() for r in reviews]


def create_review(db: Session, user_id: str, product_id: str, rating: float, comment: str = "") -> dict:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    if rating < 1 or rating > 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rating must be between 1 and 5")

    review = Review(
        id=str(uuid.uuid4()),
        user_id=user_id,
        product_id=product_id,
        rating=rating,
        comment=comment,
        created_at=datetime.now(timezone.utc),
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    reviews = db.query(Review).filter(Review.product_id == product_id).all()
    product.rating = round(sum(r.rating for r in reviews) / len(reviews), 1) if reviews else rating
    product.review_count = len(reviews)
    db.commit()

    return review.to_dict()


def get_user_reviews(db: Session, user_id: str) -> list:
    reviews = db.query(Review).filter(Review.user_id == user_id).order_by(
        Review.created_at.desc()
    ).all()
    return [r.to_dict() for r in reviews]
