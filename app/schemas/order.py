from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


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

    @field_validator("shipping_address")
    @classmethod
    def shipping_address_must_be_real(cls, value: str) -> str:
        stripped = (value or "").strip()
        # Reject blank lines and the Dart default Object.toString() artifact old
        # mobile builds sent ("Instance of 'Address'"), which carry no
        # deliverable information. Both make the order un-shippable.
        if not stripped or "Instance of '" in stripped:
            raise ValueError(
                "A valid shipping address is required. Please add and select a delivery address."
            )
        return value


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
    delivery_fee: float = 0.0
    final_amount: float
    order_status: str
    payment_status: str
    shipping_address: str | None = None
    # Customer's state locked in at checkout; printed as place of supply on the
    # GST invoice.
    shipping_state: str | None = None
    # Populated by format_order() when a return/replace has been requested; the
    # storefront reads these to reflect return state on the order screen.
    return_reason: str | None = None
    return_status: str | None = None
    return_evidence: list[str] = []
    return_admin_note: str | None = None
    estimated_delivery: datetime | None = None
    dispatched_at: datetime | None = None
    delivered_at: datetime | None = None
    return_requested_at: datetime | None = None
    return_approved_at: datetime | None = None
    return_picked_up_at: datetime | None = None
    # ShipRocket courier tracking (populated when the order is dispatched).
    awb_code: str | None = None
    courier_name: str | None = None
    shipment_status: str | None = None
    tracking_url: str | None = None
    created_at: datetime
    items: list[OrderItemResponse] = []

    class Config:
        from_attributes = True


class OrderStatusUpdate(BaseModel):
    status: str


class ReturnRequest(BaseModel):
    reason: str = ""
    # Evidence images (return URL from the upload endpoint) the customer wants
    # reviewed; optional but recommended.
    evidence: list[str] = []
