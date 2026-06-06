from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class OrderItemInput(BaseModel):
    product_id: str
    variant_id: str | None = None
    quantity: int


class OrderCreateRequest(BaseModel):
    shipping_address: str
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
