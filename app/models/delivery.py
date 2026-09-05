import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DeliverySettings(Base):
    """Store-wide delivery charge, edited from the Admin app.

    A single row (a singleton). Defaults keep delivery free until the seller
    turns it on, so existing behaviour is unchanged out of the box.

    `fee` is the default charge for any destination without a state-specific
    entry in `state_fees`. `state_fees` maps an Indian state name to its own
    delivery fee — delivery is priced by how far the parcel travels, not one
    flat rate for the whole country.
    """

    __tablename__ = "delivery_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # When False, delivery is always free regardless of fee.
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # Default delivery charge applied to an order going to an unlisted state.
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    # Per-state delivery charges: {state_name: fee_in_rupees}. A state not in
    # this map falls back to the default `fee`. NULL means "no state-specific
    # charges — every destination pays the default".
    state_fees: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Waive the fee when the cart subtotal reaches this amount. NULL disables
    # the free-over threshold (the fee then always applies).
    free_above: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
