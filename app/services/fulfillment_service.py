import random
import string
import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.order import Order
from app.models.payment import GstInvoice, Payment
from app.services import notifications
from app.services import shiprocket_service

OTP_TTL_MINUTES = 10
logger = logging.getLogger(__name__)


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
    """Mark an order dispatched and issue the delivery OTP to the customer.

    When ShipRocket is enabled AND configured, dispatching also creates the
    courier shipment (create adhoc -> assign AWB -> generate pickup) and stores
    the tracking details on the order. If that fails we still dispatch through
    the in-house OTP flow so an order is never stuck; the caller can see the
    courier error in the response and retry the courier step separately.
    """
    order = _get_order_or_404(order_id, db)
    if order.order_status in ("delivered", "cancelled"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This order cannot be dispatched")
    order.order_status = "dispatched"
    order.dispatched_at = datetime.now(timezone.utc)
    _issue_otp(order, "dispatch_otp", "dispatch_otp_expires_at")

    courier_note = None
    if shiprocket_service.is_enabled():
        try:
            _create_shiprocket_shipment(order, db)
        except shiprocket_service.ShipRocketError as e:
            courier_note = f"Courier shipment failed: {e}"

    db.commit()
    db.refresh(order)
    notifications.notify_order_dispatched(order)
    result = {
        "message": "Order dispatched",
        "delivery_otp": order.dispatch_otp,
        "expires_in_minutes": OTP_TTL_MINUTES,
        "courier": {
            "shipment_id": order.shipment_id,
"awb_code": order.awb_code,
        "courier_name": order.courier_name,
        "shipment_status": order.shipment_status,
        "tracking_url": order.tracking_url,
        # True when a ShipRocket courier order exists for this order (created
        # at checkout); lets the operator spot orders that never reached the
        # courier panel.
        "shiprocket_synced": bool(order.shiprocket_order_id),
        },
    }
    if courier_note:
        result["courier_error"] = courier_note
    return result


def _resolve_payment_method(order: Order, db: Session) -> str:
    """Return 'cod' or 'prepaid' for the ShipRocket payload.

    COD is decided by the buyer choosing Cash on Delivery at checkout; the
    payment gateway/payment_method on the Payment row records it. Everything
    else — Razorpay paid or still pending — ships as prepaid.
    """
    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    if payment is not None:
        gateway = (payment.gateway or payment.payment_method or "").lower()
        if gateway == "cod":
            return "cod"
    return "prepaid"


def _shiprocket_items(order: Order) -> list[dict]:
    return [
        {
            "product_name": it.product_name,
            "product_id": str(it.product_id),
            "variant_id": str(it.variant_id) if it.variant_id else None,
            "quantity": it.quantity,
            "price": it.price,
            "gst_amount": 0.0,
            "discount": 0.0,
        }
        for it in order.items
    ]


def sync_order_to_shiprocket(order: Order, db: Session) -> str | None:
    """Push a placed order to ShipRocket as a courier order (idempotent).

    Called as soon as the order is financially committed (COD chosen at
    checkout, or prepaid payment verified) so it shows up in the ShipRocket
    panel immediately — no admin action required. Also called again at dispatch
    if it never succeeded, or re-dispatch must not duplicate the courier order.

    Returns None on success / skip, or an error string that the caller can
    surface to the operator.
    """
    if not shiprocket_service.is_enabled() or order.shiprocket_order_id:
        return None

    try:
        created = shiprocket_service.create_order(
            order, order.user, _shiprocket_items(order), _resolve_payment_method(order, db)
        )
    except shiprocket_service.ShipRocketError as e:
        logger.warning("ShipRocket order create failed for order %s: %s", order.id, e)
        return f"Courier order not created: {e}"

    sr_order_id = created.get("order_id") or created.get("shipment_id")
    shipment_id = created.get("shipment_id")
    awb_code = created.get("awb_code")
    if sr_order_id:
        order.shiprocket_order_id = str(sr_order_id)
    if shipment_id:
        order.shipment_id = str(shipment_id)
    if awb_code:
        order.awb_code = str(awb_code)
    db.commit()
    logger.info(
        "ShipRocket order created for order %s: sr_order=%s shipment=%s awb=%s",
        order.id, sr_order_id, shipment_id, awb_code,
    )
    return None


def _create_shiprocket_shipment(order: Order, db: Session) -> None:
    """Finish the courier step at dispatch — AWB + pickup (idempotent).

    The ShipRocket order itself is normally created at checkout; dispatching
    only assigns the courier (AWB) against the existing order and schedules a
    pickup. When the order never reached ShipRocket (e.g. it predates the
    checkout hook) the adhoc order is created here first. Orders that already
    carry an AWB are left untouched so re-dispatch never duplicates shipments.
    """
    if order.awb_code:
        return

    if not order.shiprocket_order_id:
        error = sync_order_to_shiprocket(order, db)
        if error or not order.shiprocket_order_id:
            raise shiprocket_service.ShipRocketError(error or "Courier order was not created")

    sr_order_id = order.shiprocket_order_id
    shipment_id = order.shipment_id
    awb_code = order.awb_code
    courier_name = None

    # Adhoc create does not assign a courier; request the cheapest available
    # courier unless the create response already carried an AWB.
    if not awb_code and (shipment_id or sr_order_id):
        try:
            awb_resp = shiprocket_service.assign_awb(shipment_id or sr_order_id)
        except shiprocket_service.ShipRocketError:
            awb_resp = {}
        shipment_id = shipment_id or awb_resp.get("shipment_id")
        awb_code = awb_code or awb_resp.get("awb_code")
        courier_name = awb_resp.get("courier_name") or awb_resp.get("courier_id")

    if awb_code and shipment_id:
        try:
            pickup_resp = shiprocket_service.generate_pickup(shipment_id)
        except shiprocket_service.ShipRocketError:
            pickup_resp = {}
        if pickup_resp.get("pickup_scheduled_at") is None and pickup_resp.get("status") not in (True, 1, "1"):
            logger.warning(
                "ShipRocket pickup for order %s not scheduled: %s",
                order.id, pickup_resp,
            )

    if sr_order_id:
        order.shiprocket_order_id = str(sr_order_id)
    if shipment_id:
        order.shipment_id = str(shipment_id)
    if awb_code:
        order.awb_code = str(awb_code)
    if courier_name:
        order.courier_name = str(courier_name)
    if awb_code:
        order.tracking_url = f"https://shiprocket.co/tracking/{awb_code}"
        order.shipment_status = "Pickup Scheduled"
    logger.info(
        "ShipRocket shipment for order %s: sr_order=%s shipment=%s awb=%s",
        order.id, sr_order_id, shipment_id, awb_code,
    )


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
        "awb_code": order.awb_code,
        "courier_name": order.courier_name,
        "shipment_status": order.shipment_status,
        "tracking_url": order.tracking_url,
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


def get_tracking(order_id: str, db: Session) -> dict:
    """Return the stored ShipRocket tracking for an order.

    When a courier has been assigned this surfaces the latest status held in
    the app, and attempts a live refresh from ShipRocket when an AWB exists.
    """
    order = _get_order_or_404(order_id, db)
    data = {
        "order_id": str(order.id),
        "awb_code": order.awb_code,
        "courier_name": order.courier_name,
        "shipment_status": order.shipment_status,
        "tracking_url": order.tracking_url,
    }
    if order.awb_code and shiprocket_service.is_enabled():
        try:
            live = shiprocket_service.track(order.awb_code)
            data["shiprocket"] = live
            if live.get("tracking_data") and live["tracking_data"].get("ship_status"):
                data["shipment_status"] = live["tracking_data"]["ship_status"]
            order.shipment_status = data["shipment_status"]
            db.commit()
        except shiprocket_service.ShipRocketError as e:
            data["shiprocket_error"] = str(e)
    return data
