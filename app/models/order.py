import uuid
import enum
from sqlalchemy import (
    Column, String, Integer, Float, ForeignKey, JSON, Enum as SAEnum, DateTime
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base


class OrderStatus(str, enum.Enum):
    placed = "placed"
    confirmed = "confirmed"
    processing = "processing"
    dispatched = "dispatched"
    out_for_delivery = "outForDelivery"
    delivered = "delivered"
    cancelled = "cancelled"


class ReturnReplaceType(str, enum.Enum):
    return_request = "returnRequest"
    replace_request = "replaceRequest"


class ReturnReplaceStatus(str, enum.Enum):
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"
    received = "received"
    processed = "processed"


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    order_number = Column(String(50), unique=True, nullable=False)
    subtotal = Column(Float, nullable=False)
    shipping = Column(Float, default=0)
    discount = Column(Float, default=0)
    gst = Column(Float, default=0)
    total = Column(Float, nullable=False)
    status = Column(SAEnum(OrderStatus), default=OrderStatus.placed)
    address_id = Column(String, ForeignKey("addresses.id"), nullable=True)
    payment_method = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    estimated_delivery = Column(DateTime, nullable=True)
    tracking_id = Column(String(100), nullable=True)

    user = relationship("User", backref="orders")
    address = relationship("Address")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    return_replace_requests = relationship(
        "ReturnReplaceRequest", back_populates="order", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "orderNumber": self.order_number,
            "items": [item.to_dict() for item in self.items],
            "subtotal": self.subtotal,
            "shipping": self.shipping,
            "discount": self.discount,
            "gst": self.gst,
            "total": self.total,
            "status": self.status.value if self.status else "placed",
            "address": self.address.to_dict() if self.address else None,
            "paymentMethod": self.payment_method,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "estimatedDelivery": self.estimated_delivery.isoformat() if self.estimated_delivery else None,
            "trackingId": self.tracking_id,
            "returnReplaceRequests": [rr.to_dict() for rr in self.return_replace_requests],
            "isReturnReplaceEligible": self.status == OrderStatus.delivered,
        }


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    size = Column(String(50), nullable=False)
    color = Column(String(100), nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")

    def to_dict(self):
        return {
            "id": self.id,
            "product": self.product.to_dict() if self.product else None,
            "quantity": self.quantity,
            "price": self.price,
            "size": self.size,
            "color": self.color,
        }


class ReturnReplaceRequestItem(Base):
    __tablename__ = "return_replace_request_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String, ForeignKey("return_replace_requests.id"), nullable=False)
    order_item_id = Column(String, ForeignKey("order_items.id"), nullable=False)
    quantity = Column(Integer, nullable=False)

    def to_dict(self):
        return {
            "orderItemId": self.order_item_id,
            "quantity": self.quantity,
        }


class ReturnReplaceRequest(Base):
    __tablename__ = "return_replace_requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    type = Column(SAEnum(ReturnReplaceType), nullable=False)
    status = Column(SAEnum(ReturnReplaceStatus), default=ReturnReplaceStatus.submitted)
    reason = Column(String(2000), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    order = relationship("Order", back_populates="return_replace_requests")
    items = relationship(
        "ReturnReplaceRequestItem", cascade="all, delete-orphan", overlaps="order"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type.value if self.type else "returnRequest",
            "status": self.status.value if self.status else "submitted",
            "items": [item.to_dict() for item in self.items],
            "reason": self.reason,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "label": "Return" if self.type == ReturnReplaceType.return_request else "Replace",
            "statusLabel": self.status.value.capitalize() if self.status else "Submitted",
        }
