from datetime import datetime

from pydantic import BaseModel


class BannerCreate(BaseModel):
    image_url: str
    title: str | None = None
    subtitle: str | None = None
    link_url: str | None = None
    link_text: str | None = None
    sort_order: int = 0
    is_active: bool = True


class BannerUpdate(BaseModel):
    image_url: str | None = None
    title: str | None = None
    subtitle: str | None = None
    link_url: str | None = None
    link_text: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class BannerResponse(BaseModel):
    id: str
    image_url: str
    title: str | None = None
    subtitle: str | None = None
    link_url: str | None = None
    link_text: str | None = None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
