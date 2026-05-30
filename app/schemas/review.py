from pydantic import BaseModel
from typing import Optional


class CreateReviewRequest(BaseModel):
    productId: str
    rating: float
    comment: Optional[str] = ""
