from sqlalchemy.orm import Session

from app.models.delivery import DeliverySettings
from app.schemas.delivery import DeliverySettingsUpdate


def get_settings(db: Session) -> DeliverySettings:
    """Return the singleton delivery settings row, creating a default one
    (delivery free) the first time it is asked for."""
    settings = db.query(DeliverySettings).first()
    if not settings:
        settings = DeliverySettings(enabled=False, fee=0.0, free_above=None)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def compute_fee(subtotal: float, settings: DeliverySettings) -> float:
    """The delivery charge for an order with this subtotal.

    Free when delivery is turned off, the fee is zero, or the subtotal reaches
    the configured free-over threshold; otherwise the flat fee applies.
    """
    if not settings.enabled or settings.fee <= 0:
        return 0.0
    if settings.free_above is not None and subtotal >= settings.free_above:
        return 0.0
    return round(settings.fee, 2)


def update_settings(req: DeliverySettingsUpdate, db: Session) -> DeliverySettings:
    settings = get_settings(db)
    data = req.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(settings, key, value)
    # A zero/negative threshold means "no free-over rule".
    if settings.free_above is not None and settings.free_above <= 0:
        settings.free_above = None
    db.commit()
    db.refresh(settings)
    return settings
