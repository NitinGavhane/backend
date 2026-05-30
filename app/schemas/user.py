from pydantic import BaseModel
from typing import Optional


class UpdateProfileRequest(BaseModel):
    fullName: Optional[str] = None
    phone: Optional[str] = None
    avatarUrl: Optional[str] = None
