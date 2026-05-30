from pydantic import BaseModel
from typing import Optional


class CreateAddressRequest(BaseModel):
    fullName: str
    phone: str
    street: str
    city: str
    state: str
    pincode: str
    isDefault: bool = False
    type: str = "Home"


class UpdateAddressRequest(BaseModel):
    fullName: Optional[str] = None
    phone: Optional[str] = None
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    isDefault: Optional[bool] = None
    type: Optional[str] = None
