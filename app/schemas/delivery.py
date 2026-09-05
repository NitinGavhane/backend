from datetime import datetime

from pydantic import BaseModel


class DeliverySettingsResponse(BaseModel):
    enabled: bool = False
    fee: float = 0.0
    state_fees: dict[str, float] | None = None
    free_above: float | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class DeliverySettingsUpdate(BaseModel):
    enabled: bool | None = None
    fee: float | None = None
    state_fees: dict[str, float] | None = None
    free_above: float | None = None
