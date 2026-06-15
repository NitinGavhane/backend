import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.review import Review
from app.models.user import User
from app.schemas.review import ReviewCreate


def get_product_reviews(product_id: str, db: Session):
    pid = _parse_uuid(product_id, "product_id")
    reviews = db.query(Review).filter(Review.product_id == pid).order_by(Review.created_at.desc()).all()
    return [
        {
            "id": str(r.id),
            "product_id": str(r.product_id),
            "user_name": r.user_name,
            "rating": r.rating,
            "comment": r.comment,
            "created_at": r.created_at,
        }
        for r in reviews
    ]


def create_review(user_id: str, product_id: str, req: ReviewCreate, db: Session):
    pid = _parse_uuid(product_id, "product_id")
    product = db.query(Product).filter(Product.id == pid).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    existing = db.query(Review).filter(Review.user_id == user_id, Review.product_id == pid).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You have already reviewed this product")
    if req.rating < 1 or req.rating > 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rating must be between 1 and 5")
    user = db.query(User).filter(User.id == user_id).first()
    review = Review(
        product_id=pid,
        user_id=uuid.UUID(user_id),
        user_name=user.full_name if user else None,
        rating=req.rating,
        comment=req.comment,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return {
        "id": str(review.id),
        "product_id": str(review.product_id),
        "user_name": review.user_name,
        "rating": review.rating,
        "comment": review.comment,
        "created_at": review.created_at,
    }


def _parse_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid {field}: must be a valid UUID")
