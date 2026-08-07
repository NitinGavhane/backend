import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    subtotal: Mapped[float] = mapped_column(Float, default=0.0)
    gst_amount: Mapped[float] = mapped_column(Float, default=0.0)
    cgst_amount: Mapped[float] = mapped_column(Float, default=0.0)
    sgst_amount: Mapped[float] = mapped_column(Float, default=0.0)
    igst_amount: Mapped[float] = mapped_column(Float, default=0.0)
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0)
    delivery_fee: Mapped[float] = mapped_column(Float, default=0.0)
    final_amount: Mapped[float] = mapped_column(Float, default=0.0)
    order_status: Mapped[str] = mapped_column(
        Enum("placed", "processing", "dispatched", "out_for_delivery", "delivered", "cancelled", name="order_status"),
        default="placed",
    )
    payment_status: Mapped[str] = mapped_column(
        Enum("pending", "paid", "failed", "refunded", name="payment_status"),
        default="pending",
    )
    shipping_address: Mapped[str] = mapped_column(Text, nullable=True)
    # Customer's state, locked in at checkout from the selected address. Drives
    # place-of-supply on the GST invoice (intra vs inter-state split).
    shipping_state: Mapped[str] = mapped_column(String(100), nullable=True)
    return_reason: Mapped[str] = mapped_column(Text, nullable=True)
    return_status: Mapped[str] = mapped_column(String(20), nullable=True)
    # Return evidence images the customer uploads (JSON array of URLs).
    return_evidence: Mapped[str] = mapped_column(Text, nullable=True)
    # Admin note surfaced to the customer (e.g. rejection reason).
    return_admin_note: Mapped[str] = mapped_column(Text, nullable=True)
    # Delivery OTP — generated at dispatch, verified by the delivery partner
    # to mark the order delivered. Never exposed to the customer in APIs; it
    # travels by email/WhatsApp instead.
    dispatch_otp: Mapped[str] = mapped_column(String(6), nullable=True)
    dispatch_otp_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    # Return pickup OTP — generated on approval, verified at pickup.
    return_otp: Mapped[str] = mapped_column(String(6), nullable=True)
    return_otp_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    dispatched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    return_requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    return_approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    return_picked_up_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_delivery: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan")
    gst_invoice = relationship("GstInvoice", back_populates="order", uselist=False, cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    variant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[float] = mapped_column(Float, nullable=False)

    order = relationship("Order", back_populates="items")
