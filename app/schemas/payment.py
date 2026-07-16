from pydantic import BaseModel


class PaymentCreateRequest(BaseModel):
    order_id: str


class PaymentVerifyRequest(BaseModel):
    order_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class PaymentResponse(BaseModel):
    id: str
    order_id: str
    transaction_id: str | None = None
    gateway: str
    payment_method: str | None = None
    amount: float
    payment_status: str
    # Present on create — used by the client to open the Razorpay checkout.
    razorpay_order_id: str | None = None
    razorpay_key_id: str | None = None
    currency: str | None = None
    amount_paise: int | None = None

    class Config:
        from_attributes = True
