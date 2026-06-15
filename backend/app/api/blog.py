from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.blog import BlogPostListResponse, BlogPostResponse
from app.services import blog_service

router = APIRouter(prefix="/api/v1/blog", tags=["Blog"])


@router.get("", response_model=list[BlogPostListResponse])
def list_posts(db: Session = Depends(get_db)):
    return blog_service.list_posts(db)


@router.get("/{slug}", response_model=BlogPostResponse)
def get_post(slug: str, db: Session = Depends(get_db)):
    post = blog_service.get_post(slug, db)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")
    return post
