from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.blog import BlogPostResponse
from app.services import blog_service

router = APIRouter(prefix="/api/v1/blog", tags=["Blog"])


@router.get("", response_model=list[BlogPostResponse])
def list_posts(db: Session = Depends(get_db)):
    return blog_service.list_posts(db)


@router.get("/{slug}", response_model=BlogPostResponse)
def get_post(slug: str, db: Session = Depends(get_db)):
    return blog_service.get_post_by_slug(slug, db)
