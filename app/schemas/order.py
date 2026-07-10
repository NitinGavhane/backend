from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class OrderItemInput(BaseModel):
    product_id: str
    variant_id: str | None = None
    quantity: int


class OrderCreateRequest(BaseModel):
    shipping_address: str
    # Customer's state (from the selected billing/shipping address). Used to
    # decide intra-state (CGST+SGST) vs inter-state (IGST) GST. Optional so old
    # clients keep working (treated as intra-state when absent).
    shipping_state: str | None = None
    items: list[OrderItemInput]


class OrderItemResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    variant_id: str | None = None
    quantity: int
    price: float

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    id: str
    user_id: str
    order_number: str
    subtotal: float
    gst_amount: float
    cgst_amount: float = 0.0
    sgst_amount: float = 0.0
    igst_amount: float = 0.0
    discount_amount: float
    final_amount: float
    order_status: str
    payment_status: str
    shipping_address: str | None = None
    estimated_delivery: datetime | None = None
    created_at: datetime
    items: list[OrderItemResponse] = []

    class Config:
        from_attributes = True


class OrderStatusUpdate(BaseModel):
    status: str
