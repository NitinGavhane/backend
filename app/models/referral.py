import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ReferralSettings(Base):
    """Store-wide refer-and-earn programme, edited from the Admin app.

    A single row (a singleton), like DeliverySettings. `commission_percentage`
    is only the *suggested* payout: the admin approves each referred sale and
    can override the amount, so nothing is ever paid automatically.
    """

    __tablename__ = "referral_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # When False the programme is off: no new earnings are recorded and the
    # storefront stops advertising a commission.
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Suggested commission on the referred order's product subtotal.
    commission_percentage: Mapped[float] = mapped_column(Float, default=5.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ReferralEarning(Base):
    __tablename__ = "referral_earnings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    referrer_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    referred_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
    referral_code: Mapped[str] = mapped_column(String(20), nullable=True)
    purchase_amount: Mapped[float] = mapped_column(Float, default=0.0)
    reward_amount: Mapped[float] = mapped_column(Float, default=0.0)
    reward_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(Enum("pending", "approved", "rejected", "cancelled", name="reward_status"), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    referrer = relationship("User", back_populates="referral_earnings", foreign_keys=[referrer_user_id])


class ReferralShareClick(Base):
    __tablename__ = "referral_share_clicks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    referrer_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    referral_code: Mapped[str] = mapped_column(String(20), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str] = mapped_column(String(500), nullable=True)
    clicked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
