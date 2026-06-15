from datetime import datetime

from pydantic import BaseModel


class AddressCreate(BaseModel):
    full_name: str
    phone: str
    street: str
    city: str
    state: str
    zip_code: str
    country: str = "India"
    is_default: bool = False


class AddressUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = None
    is_default: bool | None = None


class AddressResponse(BaseModel):
    id: str
    user_id: str
    full_name: str
    phone: str
    street: str
    city: str
    state: str
    zip_code: str
    country: str
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True
