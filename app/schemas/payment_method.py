from pydantic import BaseModel


class PaymentMethodResponse(BaseModel):
    id: str
    name: str
    code: str
    icon_url: str | None = None
    is_active: bool
