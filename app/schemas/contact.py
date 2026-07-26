import re
from datetime import datetime

from pydantic import BaseModel, field_validator

# Deliberately not pydantic's EmailStr: that needs the email-validator package,
# which is not in requirements.txt. A shape check is enough here — these
# addresses are for replying to an enquiry, not for authentication.
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_email(value: str) -> str:
    email = (value or "").strip().lower()
    if not _EMAIL.match(email):
        raise ValueError("Enter a valid email address")
    return email


class ContactMessageCreate(BaseModel):
    full_name: str
    email: str
    subject: str | None = None
    message: str

    @field_validator("full_name", "message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("This field is required")
        return v.strip()

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        return _clean_email(v)


class ContactMessageResponse(BaseModel):
    id: str
    full_name: str
    email: str
    subject: str | None = None
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NewsletterSubscribeRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        return _clean_email(v)


class NewsletterSubscriberResponse(BaseModel):
    id: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class SubmitAck(BaseModel):
    """What the website shows the customer after a successful submit."""

    message: str
