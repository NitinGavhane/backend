import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Methods are presented to the buyer on their own terms (UPI, Cards, …); the
# gateway that actually processes them is an implementation detail the checkout
# never shows. Adding a method is a row, not a code change.
ALL_REGIONS = "*"


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Stable identifier the client sends back and Payment.payment_method records.
    # Matches the gateway's own method name (upi/card/netbanking/wallet) so it
    # can be handed straight to the checkout to preselect.
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    icon_url: Mapped[str] = mapped_column(String(500), nullable=True)
    # Which gateway processes this method. Only "razorpay" exists today; the
    # column is what lets a second gateway arrive without a schema change.
    gateway: Mapped[str] = mapped_column(String(50), default="razorpay", nullable=False)
    # Comma-separated ISO-3166-1 alpha-2 codes ("IN" or "IN,AE"), or "*" for
    # every region. UPI is India-only; cards are not.
    regions: Mapped[str] = mapped_column(String(255), default=ALL_REGIONS, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def available_in(self, region: str | None) -> bool:
        """Whether this method is offered in `region` (an alpha-2 country code)."""
        if self.regions.strip() == ALL_REGIONS:
            return True
        if not region:
            return False
        allowed = {r.strip().upper() for r in self.regions.split(",") if r.strip()}
        return region.strip().upper() in allowed
