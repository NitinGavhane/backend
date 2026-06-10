from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.category import Category
from app.schemas.category import CategoryResponse

router = APIRouter(prefix="/api/v1/categories", tags=["Categories"])


@router.get("", response_model=list[CategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    categories = db.query(Category).filter(Category.is_active == True).all()
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "slug": c.slug,
            "description": c.description,
            "image_url": c.image_url,
            "gender": c.gender,
            "is_active": c.is_active,
            "created_at": c.created_at,
        }
        for c in categories
    ]
