from pydantic import BaseModel
from typing import List, Optional


class OrderItemRequest(BaseModel):
    productId: str
    quantity: int
    size: str
    color: str


class CreateOrderRequest(BaseModel):
    items: List[OrderItemRequest]
    addressId: str
    paymentMethod: str


class ReturnReplaceItemRequest(BaseModel):
    orderItemId: str
    quantity: int


class CreateReturnReplaceRequest(BaseModel):
    type: str
    items: List[ReturnReplaceItemRequest]
    reason: str
