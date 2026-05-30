from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.review import CreateReviewRequest
from app.services import review_service

router = APIRouter(prefix="/api/reviews", tags=["Reviews"])


@router.get("/product/{product_id}")
def get_product_reviews(
    product_id: str,
    db: Session = Depends(get_db),
):
    reviews = review_service.get_product_reviews(db, product_id)
    return {"reviews": reviews}


@router.post("")
def create_review(
    req: CreateReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return review_service.create_review(db, current_user.id, req.productId, req.rating, req.comment)


@router.get("/my")
def get_my_reviews(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reviews = review_service.get_user_reviews(db, current_user.id)
    return {"reviews": reviews}
