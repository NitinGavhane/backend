from datetime import datetime

from pydantic import BaseModel, field_validator


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

    # The ORM `id` is a uuid.UUID; Pydantic v2 will not auto-coerce it to str,
    # so serializing raw ORM rows (as the coupon endpoints do) 500s. Coerce here
    # so list/get/create/update all return correctly from ORM objects.
    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id_to_str(cls, v):
        return str(v)

    class Config:
        from_attributes = True
