from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.review import ReviewCreate, ReviewResponse
from app.services import review_service

router = APIRouter(prefix="/api/v1/reviews", tags=["Reviews"])


@router.post("", response_model=ReviewResponse, status_code=201)
def create_review(req: ReviewCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return review_service.create_review(str(user.id), req, db)


@router.get("/product/{product_id}", response_model=list[ReviewResponse])
def list_reviews(product_id: str, db: Session = Depends(get_db)):
    return review_service.list_reviews(product_id, db)
