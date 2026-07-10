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
    stock: int = 0
    featured: bool = False
    is_replaceable: bool = False
    is_returnable: bool = False
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
    stock: int | None = None
    featured: bool | None = None
    is_replaceable: bool | None = None
    is_returnable: bool | None = None
    gender: str | None = None
    is_active: bool | None = None
    images: list[ProductImageCreate] | None = None


class ProductResponse(BaseModel):
    id: str
    title: str
    sku: str = ""
    brand: str | None = None
    description: str | None = None
    price: float
    original_price: float
    discount_percentage: float = 0.0
    rating: float = 0.0
    review_count: int = 0
    stock: int
    image_url: str | None = None
    category_id: str
    category_name: str | None = None
    gender: str | None = None
    sizes: list[str] = []
    colors: list[str] = []
    gradient_colors: list[str] = []
    is_featured: bool = False
    is_new: bool = False
    is_popular: bool = False
    is_replaceable: bool = False
    is_returnable: bool = False
    cgst_percentage: float = 9.0
    sgst_percentage: float = 9.0
    igst_percentage: float = 18.0
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


class AdminProductResponse(BaseModel):
    id: str
    title: str
    sku: str
    price: float
    discount_price: float | None = None
    stock: int
    featured: bool
    is_active: bool
    is_replaceable: bool = False
    is_returnable: bool = False
    category_id: str | None = None
    category_name: str | None = None
    primary_image: str | None = None
    description: str | None = None
    brand: str | None = None
    gender: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    variants: list[ProductVariantResponse] = []
    images: list[ProductImageResponse] = []

    class Config:
        from_attributes = True
