import razorpay
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.order import Order
from app.models.payment import GstInvoice, Payment


def _razorpay_client() -> razorpay.Client:
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment gateway is not configured",
        )
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def create_payment(order_id: str, db: Session) -> dict:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    payment = db.query(Payment).filter(Payment.order_id == order_id).first()
    if payment and payment.payment_status == "paid":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order already paid")

    client = _razorpay_client()
    amount_paise = int(round(order.final_amount * 100))
    rzp_order = client.order.create(
        {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": order.order_number,
            "notes": {"order_id": str(order_id)},
        }
    )

    # Reuse the existing pending Payment row on retry, otherwise create one.
    if not payment:
        payment = Payment(
            order_id=order_id,
            amount=order.final_amount,
            gateway="razorpay",
            payment_status="pending",
        )
        db.add(payment)
    payment.amount = order.final_amount
    payment.gateway = "razorpay"
    payment.gateway_order_id = rzp_order["id"]
    payment.payment_status = "pending"
    db.commit()
    db.refresh(payment)

    return {
        "id": str(payment.id),
        "order_id": str(payment.order_id),
        "amount": payment.amount,
        "gateway": payment.gateway,
        "payment_status": payment.payment_status,
        # Fields the client needs to open the Razorpay checkout.
        "razorpay_order_id": rzp_order["id"],
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        "currency": "INR",
        "amount_paise": amount_paise,
    }


def verify_payment(
    order_id: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
    db: Session,
) -> dict:
    payment = db.query(Payment).filter(Payment.order_id == order_id).first()
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
    payment.payment_method = "razorpay"
    payment.payment_status = "paid"

    order = db.query(Order).filter(Order.id == order_id).first()
    if order:
        order.payment_status = "paid"

    # One GST invoice per order — reuse if a retry already created it.
    invoice = db.query(GstInvoice).filter(GstInvoice.order_id == order_id).first()
    if invoice:
        invoice_number = invoice.invoice_number
    else:
        invoice_number = f"INV-{order.order_number}-{str(order_id)[:8].upper()}"
        db.add(GstInvoice(order_id=order_id, invoice_number=invoice_number, gst_number="GST1234567890"))

    db.commit()
    return {"message": "Payment verified successfully", "invoice_number": invoice_number}
