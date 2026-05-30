from pydantic import BaseModel


class AddToCartRequest(BaseModel):
    productId: str
    quantity: int = 1
    selectedSize: str
    selectedColor: str


class UpdateCartItemRequest(BaseModel):
    quantity: int
