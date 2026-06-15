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

    class Config:
        from_attributes = True
