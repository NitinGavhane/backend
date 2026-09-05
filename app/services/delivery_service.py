from sqlalchemy.orm import Session

from app.models.delivery import DeliverySettings
from app.schemas.delivery import DeliverySettingsUpdate

# Per-state delivery charges (₹), keyed by the Indian state name as it appears
# on the shipping address. The tiers reflect distance from the seller in West
# Bengal; the Admin app can edit every value, and any state left out of the map
# simply pays the default `fee` instead.
DEFAULT_STATE_FEES: dict[str, float] = {
    # Home state & immediate neighbours (East India)
    "West Bengal": 49.0,
    "Bihar": 49.0,
    "Jharkhand": 49.0,
    "Odisha": 49.0,
    "Sikkim": 49.0,
    # North-East India (Assam & the Seven Sisters)
    "Assam": 59.0,
    "Arunachal Pradesh": 59.0,
    "Meghalaya": 59.0,
    "Manipur": 59.0,
    "Mizoram": 59.0,
    "Nagaland": 59.0,
    "Tripura": 59.0,
    # East & Central India
    "Chhattisgarh": 69.0,
    "Madhya Pradesh": 69.0,
    "Uttar Pradesh": 69.0,
    "Uttarakhand": 69.0,
    # North India
    "Rajasthan": 79.0,
    "Delhi": 79.0,
    "Haryana": 79.0,
    "Punjab": 79.0,
    "Himachal Pradesh": 79.0,
    "Chandigarh": 79.0,
    "Jammu & Kashmir": 99.0,
    "Ladakh": 99.0,
    # West India
    "Maharashtra": 79.0,
    "Gujarat": 79.0,
    "Goa": 89.0,
    # South India
    "Karnataka": 89.0,
    "Telangana": 89.0,
    "Andhra Pradesh": 89.0,
    "Tamil Nadu": 89.0,
    "Kerala": 89.0,
    "Puducherry": 89.0,
}


def get_settings(db: Session) -> DeliverySettings:
    """Return the singleton delivery settings row, creating a default one
    (delivery free) the first time it is asked for."""
    settings = db.query(DeliverySettings).first()
    if not settings:
        settings = DeliverySettings(enabled=False, fee=0.0, free_above=None, state_fees=DEFAULT_STATE_FEES)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def fee_for_state(settings: DeliverySettings, state: str | None) -> float:
    """The delivery charge for a destination in this state.

    A state-specific entry wins; otherwise the default `fee` applies. Missing
    or blank state, out-of-India addresses, and case/spacing mismatches all fall
    back to the default fee for safety.
    """
    if not state:
        return settings.fee
    state_fees = settings.state_fees or {}
    normalized = " ".join(state.strip().title().split()).replace(" & ", " and ")
    for key, value in state_fees.items():
        normalized_key = " ".join(key.strip().title().split()).replace(" & ", " and ")
        if normalized_key == normalized:
            return value
    return settings.fee


def compute_fee(subtotal: float, settings: DeliverySettings, state: str | None = None) -> float:
    """The delivery charge for an order with this subtotal going to `state`.

    Free when delivery is turned off, the fee is zero, or the subtotal reaches
    the configured free-over threshold; otherwise the destination's fee (a
    state-specific amount when configured, else the default) applies.
    """
    if not settings.enabled or settings.fee <= 0:
        return 0.0
    if settings.free_above is not None and subtotal >= settings.free_above:
        return 0.0
    return round(fee_for_state(settings, state), 2)


def update_settings(req: DeliverySettingsUpdate, db: Session) -> DeliverySettings:
    settings = get_settings(db)
    data = req.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(settings, key, value)
    # A zero/negative threshold means "no free-over rule".
    if settings.free_above is not None and settings.free_above <= 0:
        settings.free_above = None
    # An empty map means "no state-specific charges" (falls back to the default).
    if settings.state_fees == {}:
        settings.state_fees = None
    db.commit()
    db.refresh(settings)
    return settings