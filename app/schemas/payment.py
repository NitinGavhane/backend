from pydantic import BaseModel


class PaymentCreateRequest(BaseModel):
    order_id: str


class PaymentVerifyRequest(BaseModel):
    order_id: str
    transaction_id: str
    payment_method: str | None = None


class PaymentResponse(BaseModel):
    id: str
    order_id: str
    transaction_id: str | None = None
    gateway: str
    payment_method: str | None = None
    amount: float
    payment_status: str

    class Config:
        from_attributes = True
