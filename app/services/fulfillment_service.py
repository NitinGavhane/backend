import random
import string
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.order import Order
from app.models.payment import GstInvoice, Payment
from app.services import notifications

OTP_TTL_MINUTES = 10


def _generate_otp() -> str:
    return "".join(random.choices(string.digits, k=6))


def _get_order_or_404(order_id: str, db: Session) -> Order:
    order = db.query(Order).options(joinedload(Order.user)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


def _issue_otp(order: Order, otp_field: str, expires_field: str) -> str:
    otp = _generate_otp()
    setattr(order, otp_field, otp)
    setattr(order, expires_field, datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES))
    return otp


def _verify_otp(order: Order, otp_field: str, expires_field: str, submitted: str) -> None:
    stored = getattr(order, otp_field)
    expires = getattr(order, expires_field)
    if not stored or not expires:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active code for this order")
    if submitted != stored:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect code. Please check and try again.")
    if datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This code has expired. Request a new one.")


# ── Delivery ────────────────────────────────────────────────────────────────

def list_delivery_orders(db: Session) -> list[dict]:
    """Orders that still need dispatch or are in transit (not delivered/cancelled)."""
    orders = (
        db.query(Order)
        .options(joinedload(Order.user))
        .filter(Order.order_status.in_(["placed", "processing", "dispatched", "out_for_delivery"]))
        .order_by(Order.created_at.asc())
        .all()
    )
    return [format_fulfillment_order(o) for o in orders]


def dispatch_order(order_id: str, db: Session) -> dict:
    """Mark an order dispatched and issue the delivery OTP to the customer."""
    order = _get_order_or_404(order_id, db)
    if order.order_status in ("delivered", "cancelled"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This order cannot be dispatched")
    order.order_status = "dispatched"
    order.dispatched_at = datetime.now(timezone.utc)
    _issue_otp(order, "dispatch_otp", "dispatch_otp_expires_at")
    db.commit()
    db.refresh(order)
    notifications.notify_order_dispatched(order)
    return {"message": "Order dispatched", "delivery_otp": order.dispatch_otp, "expires_in_minutes": OTP_TTL_MINUTES}


def verify_delivery_otp(order_id: str, otp: str, db: Session) -> dict:
    """Delivery partner submits the customer's OTP to confirm delivery."""
    order = _get_order_or_404(order_id, db)
    if order.order_status in ("delivered", "cancelled"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This order is already finished")
    _verify_otp(order, "dispatch_otp", "dispatch_otp_expires_at", otp)
    order.order_status = "delivered"
    order.delivered_at = datetime.now(timezone.utc)
    order.dispatch_otp = None
    order.dispatch_otp_expires_at = None
    _mark_cod_paid(order, db)
    db.commit()
    db.refresh(order)
    notifications.notify_order_delivered(order)
    return {"message": "Delivery confirmed", "order_status": "delivered"}


def _mark_cod_paid(order: Order, db: Session) -> None:
    """Close the money on a delivered Cash-on-Delivery order.

    COD is paid at the doorstep, so the payment only becomes 'paid' when the
    delivery is confirmed. This keeps GST invoices available to the customer
    for every order that actually got paid (Razorpay orders already flip to
    'paid' in verify_payment; COD needed the same treatment at delivery time).
    Only COD orders are touched — an online order still awaiting payment stays
    pending even if its status is set to delivered.
    """
    if order.payment_status == "paid":
        return

    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    is_cod = payment is not None and (
        payment.gateway == "cod" or payment.payment_method == "cod"
    )
    if not is_cod:
        return

    payment.payment_status = "paid"
    order.payment_status = "paid"

    # One GST invoice per order — reuse if a previous delivery already created it.
    invoice = db.query(GstInvoice).filter(GstInvoice.order_id == order.id).first()
    if not invoice:
        invoice_number = f"INV-{order.order_number}-{str(order.id)[:8].upper()}"
        db.add(GstInvoice(order_id=order.id, invoice_number=invoice_number, gst_number=settings.SELLER_GSTIN))


# ── Returns ─────────────────────────────────────────────────────────────────

def list_return_orders(db: Session) -> list[dict]:
    """Orders with a return/replace request, oldest first."""
    orders = (
        db.query(Order)
        .options(joinedload(Order.user))
        .filter(Order.return_status.isnot(None))
        .order_by(Order.created_at.asc())
        .all()
    )
    return [format_fulfillment_order(o) for o in orders]


def approve_return(order_id: str, db: Session) -> dict:
    """Approve a return/replace request and issue the pickup OTP."""
    order = _get_order_or_404(order_id, db)
    if not order.return_status or order.return_status in ("approved", "picked_up"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pending return request to approve")
    order.return_status = "approved"
    order.return_approved_at = datetime.now(timezone.utc)
    _issue_otp(order, "return_otp", "return_otp_expires_at")
    db.commit()
    db.refresh(order)
    notifications.notify_return_approved(order)
    return {"message": "Return approved", "pickup_otp": order.return_otp, "expires_in_minutes": OTP_TTL_MINUTES}


def reject_return(order_id: str, reason: str, db: Session) -> dict:
    """Reject a return request, keeping the reason to surface to the customer."""
    order = _get_order_or_404(order_id, db)
    if not order.return_status or order.return_status in ("approved", "picked_up"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pending return request to reject")
    if not reason or not reason.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A rejection reason is required")
    order.return_status = "rejected"
    order.return_admin_note = reason.strip()
    db.commit()
    db.refresh(order)
    notifications.notify_return_rejected(order, reason)
    return {"message": "Return rejected", "return_status": "rejected"}


def verify_return_pickup(order_id: str, otp: str, db: Session) -> dict:
    """Pickup partner submits the customer's OTP to complete the pickup."""
    order = _get_order_or_404(order_id, db)
    if order.return_status != "approved":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Return is not approved for pickup")
    _verify_otp(order, "return_otp", "return_otp_expires_at", otp)
    order.return_status = "picked_up"
    order.return_picked_up_at = datetime.now(timezone.utc)
    order.return_otp = None
    order.return_otp_expires_at = None
    db.commit()
    db.refresh(order)
    notifications.notify_return_picked_up(order)
    return {"message": "Return pickup complete", "return_status": "picked_up"}


def format_fulfillment_order(order: Order) -> dict:
    """Admin-facing order envelope for the delivery/returns dashboards.

    Includes the current OTP when one is live so the store operator can relay
    it during a transaction; never shipped to customer-facing endpoints.
    """
    data = {
        "id": str(order.id),
        "order_number": order.order_number,
        "user": {
            "id": str(order.user.id),
            "full_name": order.user.full_name,
            "email": order.user.email,
            "phone": order.user.phone,
        },
        "order_status": order.order_status,
        "payment_status": order.payment_status,
        "return_status": order.return_status,
        "return_reason": order.return_reason,
        "return_evidence": order.return_evidence,
        "return_admin_note": order.return_admin_note,
        "shipping_address": order.shipping_address,
        "final_amount": order.final_amount,
        "created_at": order.created_at,
        "dispatched_at": order.dispatched_at,
        "delivered_at": order.delivered_at,
        "return_requested_at": order.return_requested_at,
        "return_approved_at": order.return_approved_at,
        "return_picked_up_at": order.return_picked_up_at,
        "items": [
            {
                "id": str(item.id),
                "product_name": item.product_name,
                "quantity": item.quantity,
                "price": item.price,
            }
            for item in order.items
        ],
    }
    return data
