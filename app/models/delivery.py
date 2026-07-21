import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DeliverySettings(Base):
    """Store-wide delivery charge, edited from the Admin app.

    A single row (a singleton). Defaults keep delivery free until the seller
    turns it on, so existing behaviour is unchanged out of the box.
    """

    __tablename__ = "delivery_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # When False, delivery is always free regardless of fee.
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # Flat delivery charge applied to an order.
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    # Waive the fee when the cart subtotal reaches this amount. NULL disables
    # the free-over threshold (the flat fee then always applies).
    free_above: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
