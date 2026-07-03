from pydantic import BaseModel


class BannerResponse(BaseModel):
    id: str
    title: str | None = None
    subtitle: str | None = None
    image_url: str
    link_url: str | None = None
    link_text: str | None = None
    section: str
    sort_order: int
    is_active: bool = True

    class Config:
        from_attributes = True


class BannerCreate(BaseModel):
    image_url: str
    title: str | None = None
    subtitle: str | None = None
    link_url: str | None = None
    link_text: str | None = None
    section: str = "hero"
    sort_order: int = 0
    is_active: bool = True


class BannerUpdate(BaseModel):
    image_url: str | None = None
    title: str | None = None
    subtitle: str | None = None
    link_url: str | None = None
    link_text: str | None = None
    section: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None
