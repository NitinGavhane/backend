from datetime import datetime

from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None
    parent_id: str | None = None
    gender: str = "unisex"


class CategoryUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    image_url: str | None = None
    parent_id: str | None = None
    gender: str | None = None
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None
    # Derived server-side from image_url; not accepted on create/update.
    storage_type: str | None = None
    file_name: str | None = None
    uploaded_at: datetime | None = None
    parent_id: str | None = None
    gender: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
