from pydantic import BaseModel
from typing import Optional


class ProductFilterParams(BaseModel):
    category: Optional[str] = None
    minPrice: Optional[float] = None
    maxPrice: Optional[float] = None
    sizes: Optional[str] = None
    colors: Optional[str] = None
    sortBy: Optional[str] = None
    page: int = 1
    limit: int = 20
