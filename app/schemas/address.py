from datetime import datetime

from pydantic import BaseModel


class AddressCreate(BaseModel):
    full_name: str
    phone: str
    street: str
    city: str
    state: str
    pincode: str
    type: str = "Home"
    is_default: bool = False


class AddressUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    street: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    type: str | None = None
    is_default: bool | None = None


class AddressResponse(BaseModel):
    id: str
    full_name: str
    phone: str
    street: str
    city: str
    state: str
    pincode: str
    type: str
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True
