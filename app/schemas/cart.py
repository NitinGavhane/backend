from pydantic import BaseModel


class CartAddRequest(BaseModel):
    product_id: str
    variant_id: str | None = None
    quantity: int = 1


class CartUpdateRequest(BaseModel):
    cart_item_id: str
    quantity: int


class CartItemResponse(BaseModel):
    id: str
    product_id: str
    product_title: str | None = None
    variant_id: str | None = None
    variant_info: str | None = None
    quantity: int
    price: float | None = None
    image_url: str | None = None

    class Config:
        from_attributes = True


class CartResponse(BaseModel):
    items: list[CartItemResponse] = []
    total: float = 0.0
