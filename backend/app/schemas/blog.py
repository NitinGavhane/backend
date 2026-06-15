from datetime import datetime

from pydantic import BaseModel


class BlogPostResponse(BaseModel):
    id: str
    title: str
    slug: str
    content: str
    excerpt: str | None = None
    image_url: str | None = None
    author: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BlogPostListResponse(BaseModel):
    id: str
    title: str
    slug: str
    excerpt: str | None = None
    image_url: str | None = None
    author: str
    created_at: datetime

    class Config:
        from_attributes = True
