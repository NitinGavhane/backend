from datetime import datetime

from pydantic import BaseModel


class CouponCreate(BaseModel):
    code: str
    type: str = "percentage"
    value: float
    min_order_amount: float | None = None
    max_discount: float | None = None
    expiry_date: str | None = None
    usage_limit: int = 100
    is_active: bool = True


class CouponUpdate(BaseModel):
    code: str | None = None
    type: str | None = None
    value: float | None = None
    min_order_amount: float | None = None
    max_discount: float | None = None
    expiry_date: str | None = None
    usage_limit: int | None = None
    is_active: bool | None = None


class CouponResponse(BaseModel):
    id: str
    code: str
    type: str
    value: float
    min_order_amount: float | None = None
    max_discount: float | None = None
    expiry_date: str | None = None
    usage_limit: int
    used_count: int = 0
    is_active: bool
    created_at: datetime | None = None

    class Config:
        from_attributes = True
