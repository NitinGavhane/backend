import logging
import uuid

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.order import Order
from app.models.payment import GstInvoice, Payment
from app.models.payment_method import PaymentMethod
from app.models.user import User
from app.services import fulfillment_service

logger = logging.getLogger(__name__)

# Cashfree creates a fresh order per payment attempt (like Razorpay did), so an
# expired/cancelled checkout can be retried without ratelimit collisions.
CASHFREE_API_VERSION = "2023-08-01"


def _cashfree_headers() -> dict[str, str]:
    if not settings.CASHFREE_CLIENT_ID or not settings.CASHFREE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment gateway is not configured",
        )
    return {
        "x-client-id": settings.CASHFREE_CLIENT_ID,
        "x-client-secret": settings.CASHFREE_CLIENT_SECRET,
        "x-api-version": CASHFREE_API_VERSION,
        "x-request-id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


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


def _cashfree_order_id(order: Order, payment: Payment) -> str:
    """Merchant order id we send to Cashfree.

    Must be alphanumeric plus '-'/'_' (3-45 chars) and unique per attempt. Our
    order number fits the character set, and appending a short payment-derived
    suffix keeps retries distinct so a second attempt never collides.
    """
    return f"DF{payment.id.hex[:14].upper()}{uuid.uuid4().hex[:4].upper()}"


def _customer_details(user: User, order: Order) -> dict:
    """Customer block Cashfree requires on every order.

    Cashfree insists on a customer_id plus at least a phone or email; our users
    always have an email and usually a phone, but a phone-less profile falls
    back to email-only without crashing checkout.
    """
    details: dict = {
        "customer_id": str(user.id).replace("-", ""),
        "customer_email": user.email,
    }
    if user.phone:
        details["customer_phone"] = user.phone
    if user.full_name:
        details["customer_name"] = user.full_name
    return details


def _return_url(order: Order) -> str:
    """Where the customer comes back to after paying on Cashfree's page.

    `{order_id}` is Cashfree's substitution token — it is replaced with the
    merchant order id at redirect time, which the storefront reads back. Our
    internal order uuid rides along as `ref` so the checkout return page can
    post both to /payments/verify (which scopes the record to the owner).
    """
    base = settings.CASHFREE_RETURN_URL or f"{settings.SITE_URL}/checkout/return"
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}order_id={{order_id}}&ref={str(order.id)}"


def create_payment(order_id: str, method_code: str | None, user_id: uuid.UUID, db: Session) -> dict:
    order = _owned_order(order_id, user_id, db)
    method = _resolve_method(method_code, db)
    user = db.query(User).filter(User.id == user_id).first()

    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    if payment and payment.payment_status == "paid":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order already paid")

    # Cash on Delivery needs no gateway: the order stands and the money changes
    # hands when the parcel arrives. Without this branch every COD attempt would
    # still demand a Cashfree order, failing the checkout whenever the store
    # has no gateway keys configured.
    is_cod = method is not None and (method.code == "cod" or method.gateway == "cod")

    if is_cod:
        if not payment:
            payment = Payment(
                order_id=order.id,
                amount=order.final_amount,
                gateway="cod",
                payment_method="cod",
                payment_status="pending",
            )
            db.add(payment)
        else:
            payment.amount = order.final_amount
            payment.gateway = "cod"
            payment.payment_method = "cod"
            payment.gateway_order_id = None
            payment.payment_status = "pending"
        db.commit()
        db.refresh(payment)
        try:
            sync_err = fulfillment_service.sync_order_to_shiprocket(order, db)
            if sync_err:
                logger.warning("COD order %s: %s", order.order_number, sync_err)
        except Exception:
            logger.exception("ShipRocket sync failed for COD order %s", order.order_number)
        try:
            from app.services import order_service  # local: order_service lazily imports payment_service
            order_service.finalize_order_as_placed(str(order.id), db)
        except Exception:
            logger.exception("COD finalize failed for order %s", order.order_number)
        return {
            "id": str(payment.id),
            "order_id": str(payment.order_id),
            "amount": payment.amount,
            "gateway": "cod",
            "payment_method": "cod",
            "payment_status": payment.payment_status,
            "cod": True,
            "currency": "INR",
            "amount_paise": int(round(order.final_amount * 100)),
        }

    # Reuse the existing pending Payment row on retry, otherwise create one.
    if not payment:
        payment = Payment(
            order_id=order.id,
            amount=order.final_amount,
            gateway="cashfree",
            payment_status="pending",
        )
        db.add(payment)
    payment.amount = order.final_amount
    payment.gateway = (method.gateway if method else "cashfree")
    # The buyer's choice, recorded up front. verify_payment replaces this with
    # whatever they actually paid with, which can differ.
    payment.payment_method = method.code if method else None
    payment.payment_status = "pending"
    db.commit()
    db.refresh(payment)

    cf_order_id = _cashfree_order_id(order, payment)
    amount = round(order.final_amount, 2)

    payload = {
        "order_id": cf_order_id,
        "order_amount": amount,
        "order_currency": "INR",
        "customer_details": _customer_details(user, order),
        "order_meta": {"return_url": _return_url(order)},
        "order_note": f"Order {order.order_number}",
    }
    try:
        resp = httpx.post(
            f"{settings.cashfree_base_url}/orders",
            headers=_cashfree_headers(),
            json=payload,
            timeout=30,
        )
    except httpx.HTTPError as exc:
        logger.error("Cashfree order create HTTP error for %s: %s", order.order_number, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The payment gateway is not reachable right now. Please try again.",
        )

    if resp.status_code != 200:
        logger.error(
            "Cashfree order create failed for %s: %s %s", order.order_number, resp.status_code, resp.text
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The payment gateway could not create this order. Please try again.",
        )

    data = resp.json()
    payment_session_id = data.get("payment_session_id", "")
    if not payment_session_id:
        logger.error("Cashfree order create missing payment_session_id: %s", data)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The payment gateway returned an incomplete order. Please try again.",
        )
    payment.gateway_order_id = cf_order_id
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
        "payment_session_id": payment_session_id,
        "cashfree_order_id": cf_order_id,
        "cashfree_environment": settings.CASHFREE_ENV.lower(),
        "return_url": _return_url(order),
        "currency": "INR",
        "amount_paise": int(round(order.final_amount * 100)),
        "cod": False,
    }


def _method_from_payment_group(payment_group: str | None, fallback: str | None) -> str | None:
    """Map Cashfree's payment_group to our payment-method codes.

    The buyer can pick UPI on our screen and then pay by card inside Cashfree's
    checkout, so the selection is a hint, not a record. An unmapped group
    (e.g. debit_card_emi) keeps whatever the buyer originally chose.
    """
    mapping = {
        "upi": "upi",
        "upi_ppi": "upi",
        "credit_card": "card",
        "debit_card": "card",
        "prepaid_card": "card",
        "net_banking": "netbanking",
        "wallet": "wallet",
        "cardless_emi": "cardless_emi",
        "pay_later": "paylater",
    }
    return mapping.get(payment_group or "", fallback)


def verify_payment(
    order_id: str,
    cashfree_order_id: str,
    user_id: uuid.UUID,
    db: Session,
) -> dict:
    """Confirm with Cashfree that the order was actually paid, then settle it.

    The client never proves anything — its checkout returns the merchant order
    id and we re-check the order's status at Cashfree before touching state.
    Persistent outbound calls (ShipRocket sync, GST invoice) mirror the old
    Razorpay path so behaviour after a successful payment is unchanged.
    """
    order = _owned_order(order_id, user_id, db)
    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    if payment.gateway_order_id != cashfree_order_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment order does not match this order",
        )
    if payment.payment_status == "paid":
        invoice = db.query(GstInvoice).filter(GstInvoice.order_id == order.id).first()
        invoice_number = invoice.invoice_number if invoice else None
        return {
            "message": "Payment already verified",
            "invoice_number": invoice_number,
            "payment_method": payment.payment_method,
        }

    try:
        resp = httpx.get(
            f"{settings.cashfree_base_url}/orders/{cashfree_order_id}/payments",
            headers=_cashfree_headers(),
            timeout=30,
        )
    except httpx.HTTPError as exc:
        logger.error("Cashfree payment status error for %s: %s", order.order_number, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not confirm payment status right now. Please retry.",
        )

    if resp.status_code != 200:
        logger.error(
            "Cashfree status fetch failed for %s: %s %s", order.order_number, resp.status_code, resp.text
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not confirm payment status right now. Please retry.",
        )

    payments = resp.json()
    successful = [
        p for p in payments if isinstance(p, dict) and p.get("payment_status") == "SUCCESS"
    ]
    if not successful:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment not completed. If you were charged, contact support.",
        )

    # The most recent successful payment tells us what they really used.
    successful.sort(key=lambda p: (p.get("payment_completion_time") or ""), reverse=True)
    payment_group = successful[0].get("payment_group")
    payment.transaction_id = str(successful[0].get("cf_payment_id") or "")
    payment.payment_method = _method_from_payment_group(payment_group, payment.payment_method)
    payment.payment_status = "paid"
    order.payment_status = "paid"
    # A 30-minute-unpaid order auto-cancels. If the customer still completes the
    # checkout afterwards, the money must not sit on a cancelled order — reopen
    # it as placed so it is fulfilled like any other paid order.
    if order.order_status == "cancelled":
        order.order_status = "placed"

    # One GST invoice per order — reuse if a retry already created it.
    invoice = db.query(GstInvoice).filter(GstInvoice.order_id == order.id).first()
    if invoice:
        invoice_number = invoice.invoice_number
    else:
        invoice_number = f"INV-{order.order_number}-{str(order.id)[:8].upper()}"
        db.add(GstInvoice(order_id=order.id, invoice_number=invoice_number, gst_number=settings.SELLER_GSTIN))

    db.commit()
    try:
        sync_err = fulfillment_service.sync_order_to_shiprocket(order, db)
        if sync_err:
            logger.warning("Paid order %s: %s", order.order_number, sync_err)
    except Exception:
        logger.exception("ShipRocket sync failed for paid order %s", order.order_number)
    try:
        from app.services import order_service  # local: order_service lazily imports payment_service
        order_service.finalize_order_as_placed(str(order.id), db)
    except Exception:
        logger.exception("Finalize failed for paid order %s", order.order_number)
    return {
        "message": "Payment verified successfully",
        "invoice_number": invoice_number,
        "payment_method": payment.payment_method,
    }


def refund_payment(order: Order, db: Session) -> str | None:
    """Refund a paid order back through Cashfree.

    Returns None when Cashfree accepted the refund (the payment is marked
    'refunded'), or a human-readable note when it could not be done
    automatically so the store handles it manually. Never raises — cancellation
    must succeed even when the gateway is unreachable. The caller commits.
    """
    if order.payment_status != "paid":
        return None
    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    if not payment or not payment.gateway_order_id:
        return "This order was not paid through the online gateway, so the refund must be processed manually."
    cf_order_id = payment.gateway_order_id
    payload = {
        "refund_id": f"RF{payment.id.hex[:14].upper()}{uuid.uuid4().hex[:4].upper()}",
        "refund_amount": round(order.final_amount, 2),
        "refund_note": f"Order {order.order_number} cancelled",
    }
    try:
        resp = httpx.post(
            f"{settings.cashfree_base_url}/orders/{cf_order_id}/refunds",
            headers=_cashfree_headers(),
            json=payload,
            timeout=30,
        )
    except httpx.HTTPError as exc:
        logger.error("Cashfree refund HTTP error for %s: %s", order.order_number, exc)
        return "The refund could not be initiated right now — our team will refund you shortly."
    if resp.status_code not in (200, 201):
        logger.error("Cashfree refund failed for %s: %s %s", order.order_number, resp.status_code, resp.text)
        return "The refund could not be initiated right now — our team will refund you shortly."
    data = resp.json()
    refund_status = (data.get("refund_status") or "").upper()
    if refund_status in ("SUCCESS", "PENDING", "PROCESSING"):
        payment.payment_status = "refunded"
        order.payment_status = "refunded"
        return None
    logger.warning("Cashfree refund not confirmed for %s: %s", order.order_number, data)
    return "The refund could not be confirmed right now — our team will follow up."