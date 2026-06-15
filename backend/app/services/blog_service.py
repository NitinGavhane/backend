from sqlalchemy.orm import Session

from app.models.blog import BlogPost


def list_posts(db: Session) -> list[dict]:
    posts = db.query(BlogPost).filter(BlogPost.is_published == True).order_by(BlogPost.created_at.desc()).all()
    return [_post_to_dict(p) for p in posts]


def get_post(slug: str, db: Session) -> dict | None:
    post = db.query(BlogPost).filter(BlogPost.slug == slug, BlogPost.is_published == True).first()
    if not post:
        return None
    return _post_to_dict(post)


def _post_to_dict(post: BlogPost) -> dict:
    return {
        "id": str(post.id),
        "title": post.title,
        "slug": post.slug,
        "content": post.content,
        "excerpt": post.excerpt,
        "image_url": post.image_url,
        "author": post.author,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
    }
