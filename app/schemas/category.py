from datetime import datetime

from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    image_url: str | None = None
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
