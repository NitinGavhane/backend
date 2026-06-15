from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.blog import BlogPost


def list_posts(db: Session):
    posts = db.query(BlogPost).filter(BlogPost.is_published == True).order_by(BlogPost.created_at.desc()).all()
    return [
        {
            "id": str(p.id),
            "title": p.title,
            "slug": p.slug,
            "excerpt": p.excerpt,
            "content": p.content,
            "image_url": p.image_url,
            "author": p.author,
            "created_at": p.created_at,
        }
        for p in posts
    ]


def get_post_by_slug(slug: str, db: Session):
    post = db.query(BlogPost).filter(BlogPost.slug == slug, BlogPost.is_published == True).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog post not found")
    return {
        "id": str(post.id),
        "title": post.title,
        "slug": post.slug,
        "excerpt": post.excerpt,
        "content": post.content,
        "image_url": post.image_url,
        "author": post.author,
        "created_at": post.created_at,
    }
