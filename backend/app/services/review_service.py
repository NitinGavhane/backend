from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.review import Review
from app.schemas.review import ReviewCreate


def create_review(user_id: str, req: ReviewCreate, db: Session) -> dict:
    product = db.query(Product).filter(Product.id == req.product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if req.rating < 1 or req.rating > 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rating must be between 1 and 5")
    existing = db.query(Review).filter(Review.product_id == req.product_id, Review.user_id == user_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You have already reviewed this product")
    review = Review(product_id=req.product_id, user_id=user_id, rating=req.rating, comment=req.comment)
    db.add(review)
    db.commit()
    db.refresh(review)
    return _review_to_dict(review, db)


def list_reviews(product_id: str, db: Session) -> list[dict]:
    reviews = db.query(Review).filter(Review.product_id == product_id).order_by(Review.created_at.desc()).all()
    return [_review_to_dict(r, db) for r in reviews]


def _review_to_dict(review: Review, db: Session) -> dict:
    from app.models.user import User
    user = db.query(User).filter(User.id == review.user_id).first()
    return {
        "id": str(review.id),
        "product_id": str(review.product_id),
        "user_id": str(review.user_id),
        "user_name": user.full_name if user else None,
        "rating": review.rating,
        "comment": review.comment,
        "created_at": review.created_at,
    }
