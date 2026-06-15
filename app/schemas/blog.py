from datetime import datetime

from pydantic import BaseModel


class BlogPostResponse(BaseModel):
    id: str
    title: str
    slug: str
    excerpt: str | None = None
    content: str | None = None
    image_url: str | None = None
    author: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
