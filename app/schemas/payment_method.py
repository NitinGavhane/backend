from pydantic import BaseModel


class PaymentMethodResponse(BaseModel):
    id: str
    name: str
    code: str
    description: str | None = None
    icon_url: str | None = None
    is_active: bool

    class Config:
        from_attributes = True


class AdminPaymentMethodResponse(PaymentMethodResponse):
    """Adds the fields only an admin configures. The buyer-facing response
    deliberately omits gateway/regions — the checkout shows methods, never the
    gateway behind them."""

    gateway: str
    regions: str
    sort_order: int


class PaymentMethodCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    icon_url: str | None = None
    gateway: str = "razorpay"
    regions: str = "*"
    is_active: bool = True
    sort_order: int = 0


class PaymentMethodUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    description: str | None = None
    icon_url: str | None = None
    gateway: str | None = None
    regions: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None
