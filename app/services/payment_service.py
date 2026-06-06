from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.payment import GstInvoice, Payment


def create_payment(order_id: str, db: Session) -> dict:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    payment = Payment(
        order_id=order_id,
        amount=order.final_amount,
        gateway="razorpay",
        payment_status="pending",
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return {
        "id": str(payment.id),
        "order_id": str(payment.order_id),
        "amount": payment.amount,
        "gateway": payment.gateway,
        "payment_status": payment.payment_status,
    }


def verify_payment(order_id: str, transaction_id: str, payment_method: str | None, db: Session) -> dict:
    payment = db.query(Payment).filter(Payment.order_id == order_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    payment.transaction_id = transaction_id
    payment.payment_method = payment_method
    payment.payment_status = "paid"

    order = db.query(Order).filter(Order.id == order_id).first()
    if order:
        order.payment_status = "paid"

    invoice_number = f"INV-{order.order_number}-{order_id[:8].upper()}"
    invoice = GstInvoice(
        order_id=order_id,
        invoice_number=invoice_number,
        gst_number="GST1234567890",
    )
    db.add(invoice)
    db.commit()

    return {"message": "Payment verified successfully", "invoice_number": invoice_number}
