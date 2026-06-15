from datetime import datetime

from pydantic import BaseModel


class ReviewCreate(BaseModel):
    product_id: str
    rating: int
    comment: str | None = None


class ReviewResponse(BaseModel):
    id: str
    product_id: str
    user_id: str
    user_name: str | None = None
    rating: int
    comment: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
