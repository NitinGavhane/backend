import uuid

import razorpay
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.order import Order
from app.models.payment import GstInvoice, Payment
from app.models.payment_method import PaymentMethod


def _razorpay_client() -> razorpay.Client:
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment gateway is not configured",
        )
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def _owned_order(order_id: str, user_id: uuid.UUID, db: Session) -> Order:
    """Load an order that belongs to this user.

    Scoping the lookup by user_id is what stops one buyer paying against — or
    verifying — another buyer's order by guessing its id. A foreign order is
    reported as 404 rather than 403 so the endpoint does not confirm that an
    order id exists.
    """
    try:
        oid = uuid.UUID(str(order_id))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid order_id")
    order = db.query(Order).filter(Order.id == oid, Order.user_id == user_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


def _resolve_method(method_code: str | None, db: Session) -> PaymentMethod | None:
    """Validate the buyer's chosen method against the configured ones.

    An unknown or disabled code is rejected rather than silently ignored — the
    alternative is charging through a method the store has switched off.
    """
    if not method_code:
        return None
    method = (
        db.query(PaymentMethod)
        .filter(PaymentMethod.code == method_code, PaymentMethod.is_active == True)  # noqa: E712
        .first()
    )
    if not method:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That payment method is not available",
        )
    return method


def create_payment(order_id: str, method_code: str | None, user_id: uuid.UUID, db: Session) -> dict:
    order = _owned_order(order_id, user_id, db)
    method = _resolve_method(method_code, db)

    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    if payment and payment.payment_status == "paid":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order already paid")

    client = _razorpay_client()
    amount_paise = int(round(order.final_amount * 100))
    rzp_order = client.order.create(
        {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": order.order_number,
            "notes": {"order_id": str(order.id)},
        }
    )

    # Reuse the existing pending Payment row on retry, otherwise create one.
    if not payment:
        payment = Payment(
            order_id=order.id,
            amount=order.final_amount,
            gateway="razorpay",
            payment_status="pending",
        )
        db.add(payment)
    payment.amount = order.final_amount
    payment.gateway = method.gateway if method else "razorpay"
    # The buyer's choice, recorded up front. verify_payment replaces this with
    # whatever they actually paid with, which can differ.
    payment.payment_method = method.code if method else None
    payment.gateway_order_id = rzp_order["id"]
    payment.payment_status = "pending"
    db.commit()
    db.refresh(payment)

    return {
        "id": str(payment.id),
        "order_id": str(payment.order_id),
        "amount": payment.amount,
        "gateway": payment.gateway,
        "payment_method": payment.payment_method,
        "payment_status": payment.payment_status,
        # Fields the client needs to open the gateway checkout.
        "razorpay_order_id": rzp_order["id"],
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        "currency": "INR",
        "amount_paise": amount_paise,
    }


def _method_actually_used(client, razorpay_payment_id: str, fallback: str | None) -> str | None:
    """Ask the gateway which method was really used.

    The buyer can pick UPI on our screen and then pay by card inside the
    gateway's sheet, so the selection is a hint, not a record. If the lookup
    fails we keep the hint rather than failing an otherwise-verified payment.
    """
    try:
        details = client.payment.fetch(razorpay_payment_id)
        return details.get("method") or fallback
    except Exception:
        return fallback


def verify_payment(
    order_id: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
    user_id: uuid.UUID,
    db: Session,
) -> dict:
    order = _owned_order(order_id, user_id, db)
    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    client = _razorpay_client()
    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )
    except razorpay.errors.SignatureVerificationError:
        payment.payment_status = "failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment signature verification failed",
        )

    payment.transaction_id = razorpay_payment_id
    payment.gateway_order_id = razorpay_order_id
    payment.payment_method = _method_actually_used(client, razorpay_payment_id, payment.payment_method)
    payment.payment_status = "paid"
    order.payment_status = "paid"

    # One GST invoice per order — reuse if a retry already created it.
    invoice = db.query(GstInvoice).filter(GstInvoice.order_id == order.id).first()
    if invoice:
        invoice_number = invoice.invoice_number
    else:
        invoice_number = f"INV-{order.order_number}-{str(order.id)[:8].upper()}"
        db.add(GstInvoice(order_id=order.id, invoice_number=invoice_number, gst_number="GST1234567890"))

    db.commit()
    return {
        "message": "Payment verified successfully",
        "invoice_number": invoice_number,
        "payment_method": payment.payment_method,
    }
