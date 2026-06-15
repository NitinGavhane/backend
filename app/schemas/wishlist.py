from datetime import datetime

from pydantic import BaseModel


class WishlistAddRequest(BaseModel):
    product_id: str


class WishlistItemResponse(BaseModel):
    id: str
    product_id: str
    product_title: str | None = None
    price: float | None = None
    image_url: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
