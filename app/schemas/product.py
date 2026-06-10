from datetime import datetime

from pydantic import BaseModel


class ProductVariantCreate(BaseModel):
    size: str | None = None
    color: str | None = None
    stock: int = 0
    price: float | None = None


class ProductVariantResponse(BaseModel):
    id: str
    size: str | None = None
    color: str | None = None
    stock: int
    price: float | None = None

    class Config:
        from_attributes = True


class ProductImageCreate(BaseModel):
    image_url: str
    is_primary: bool = False


class ProductImageResponse(BaseModel):
    id: str
    image_url: str
    is_primary: bool

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    category_id: str
    title: str
    description: str | None = None
    brand: str | None = None
    sku: str
    price: float
    discount_price: float | None = None
    gst_percentage: float = 18.0
    stock: int = 0
    featured: bool = False
    gender: str | None = None
    variants: list[ProductVariantCreate] = []
    images: list[ProductImageCreate] = []


class ProductUpdate(BaseModel):
    category_id: str | None = None
    title: str | None = None
    description: str | None = None
    brand: str | None = None
    sku: str | None = None
    price: float | None = None
    discount_price: float | None = None
    gst_percentage: float | None = None
    stock: int | None = None
    featured: bool | None = None
    gender: str | None = None
    is_active: bool | None = None
    images: list[ProductImageCreate] | None = None


class ProductResponse(BaseModel):
    id: str
    category_id: str
    title: str
    description: str | None = None
    brand: str | None = None
    sku: str
    price: float
    discount_price: float | None = None
    gst_percentage: float
    stock: int
    featured: bool
    is_active: bool
    gender: str
    created_at: datetime
    updated_at: datetime
    variants: list[ProductVariantResponse] = []
    images: list[ProductImageResponse] = []

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    id: str
    title: str
    sku: str
    price: float
    discount_price: float | None = None
    stock: int
    featured: bool
    is_active: bool
    gender: str
    category_name: str | None = None
    primary_image: str | None = None

    class Config:
        from_attributes = True
