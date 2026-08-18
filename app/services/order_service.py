import json
import random
import string
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core import gst
from app.services import delivery_service, referral_service, notifications
from app.models.cart import CartItem
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.referral import ReferralEarning
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.schemas.order import OrderCreateRequest

# Unpaid orders are auto-cancelled after this window and their reserved stock
# released, so an abandoned checkout can't hold inventory hostage forever.
PENDING_PAYMENT_TTL_MINUTES = 30


def generate_order_number() -> str:
    return "ORD-" + datetime.now().strftime("%Y%m%d") + "-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def create_order(user_id: str, req: OrderCreateRequest, db: Session):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Read delivery settings up front — before any stock is decremented — so the
    # one-time default-row creation can't commit a half-built order.
    delivery_settings = delivery_service.get_settings(db)

    subtotal = 0.0
    order_items_data = []

    for item_input in req.items:
        product = db.query(Product).filter(Product.id == item_input.product_id, Product.is_active == True).first()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {item_input.product_id} not found")
        if product.stock < item_input.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Insufficient stock for {product.title}")
        unit_price = product.discount_price or product.price
        item_subtotal = unit_price * item_input.quantity
        subtotal += item_subtotal
        order_items_data.append({
            "product_id": product.id,
            "variant_id": item_input.variant_id,
            "product_name": product.title,
            "quantity": item_input.quantity,
            "price": unit_price,
        })
        product.stock -= item_input.quantity

    # Place-of-supply GST: intra-state (CGST+SGST) if the customer is in the
    # seller's state, otherwise inter-state (IGST). Decided from the order's
    # shipping-address state — the seller (West Bengal) is fixed.
    subtotal = round(subtotal, 2)
    breakup = gst.gst_breakup(subtotal, req.shipping_state)
    # Delivery charge from the store-wide settings (free unless the seller has
    # configured a fee; waived above the free-over threshold).
    delivery_fee = delivery_service.compute_fee(subtotal, delivery_settings)
    final_amount = subtotal + breakup["gst_amount"] + delivery_fee
    estimated_delivery = datetime.now(timezone.utc) + timedelta(days=7)

    # An order is born "awaiting payment", not "placed" — it only becomes a real
    # order the moment the money is committed (COD chosen at checkout, or an
    # online payment verified). The confirmation email and referral recording
    # happen in finalize_order_as_placed so an abandoned checkout records nothing.
    order = Order(
        user_id=user_id,
        order_number=generate_order_number(),
        subtotal=subtotal,
        gst_amount=breakup["gst_amount"],
        cgst_amount=breakup["cgst_amount"],
        sgst_amount=breakup["sgst_amount"],
        igst_amount=breakup["igst_amount"],
        discount_amount=0.0,
        delivery_fee=delivery_fee,
        final_amount=round(final_amount, 2),
        order_status="pending_payment",
        shipping_address=req.shipping_address,
        shipping_state=req.shipping_state,
        estimated_delivery=estimated_delivery,
    )
    db.add(order)
    db.flush()

    for item_data in order_items_data:
        order_item = OrderItem(order_id=order.id, **item_data)
        db.add(order_item)

    db.flush()

    db.commit()
    db.refresh(order)
    return get_order_detail(str(order.id), db)


def finalize_order_as_placed(order_id: str, db: Session):
    """Flip an awaiting-payment order to placed the moment it is financially committed.

    Called by the payment service once payment is settled (COD confirmed at
    checkout, or an online payment verified). This is where the referral and
    the confirmation email fire — an abandoned checkout must never record a
    referral or tell the customer their order is placed.
    """
    order = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.order_status != "pending_payment":
        return
    order.order_status = "placed"
    first_product_id = order.items[0].product_id if order.items else None
    user = db.query(User).filter(User.id == order.user_id).first()
    if user:
        referral_service.record_first_order_referral(user, order, order.subtotal, first_product_id, db)
    db.commit()
    db.refresh(order)
    try:
        notifications.notify_order_placed(order)
    except Exception:
        pass


def get_user_orders(user_id: str, db: Session):
    expire_stale_pending_orders(db)
    orders = db.query(Order).options(joinedload(Order.items)).filter(Order.user_id == user_id).order_by(Order.created_at.desc()).all()
    return [format_order(o) for o in orders]


def get_order_detail(order_id: str, db: Session):
    order = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return format_order(order)


def update_order_status(order_id: str, status_str: str, db: Session):
    valid_statuses = ["placed", "processing", "dispatched", "out_for_delivery", "delivered", "cancelled"]
    if status_str not in valid_statuses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status. Must be one of: {valid_statuses}")
    order = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if status_str == "cancelled":
        # Admin-initiated cancellation runs through the same path as a customer
        # cancel: stock back on the shelf, paid orders refunded through Cashfree.
        _perform_cancel(order, db, "Your order was cancelled by the store.")
        return format_order(order)
    order.order_status = status_str
    db.commit()
    db.refresh(order)
    return format_order(order)


def cancel_order(user_id: str, order_id: str, db: Session) -> dict:
    """Customer-initiated cancellation for orders that have not been dispatched."""
    order = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id, Order.user_id == user_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.order_status in ("dispatched", "out_for_delivery", "delivered"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This order has already been dispatched and can no longer be cancelled.",
        )
    if order.order_status == "cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This order is already cancelled.")
    paid = order.payment_status == "paid"
    refund_note = _perform_cancel(order, db, "Your order was cancelled as requested.")
    message = "Order cancelled."
    if paid:
        message += f" {refund_note}" if refund_note else " A refund has been initiated to your original payment method."
    return {"message": message, "order_status": "cancelled", "refund": refund_note}


def expire_stale_pending_orders(db: Session) -> int:
    """Cancel awaiting-payment orders older than 30 minutes and release stock.

    There is no background worker, so the sweep is lazy: every order/delivery
    listing calls it first, keeping stragglers from lingering forever.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=PENDING_PAYMENT_TTL_MINUTES)
    stale = (
        db.query(Order)
        .options(joinedload(Order.items))
        .filter(Order.order_status == "pending_payment", Order.created_at < cutoff)
        .all()
    )
    for order in stale:
        _perform_cancel(
            order,
            db,
            "Payment was not completed within 30 minutes, so this order was automatically cancelled and the items released.",
        )
    return len(stale)


def _restore_stock(order: Order, db: Session) -> None:
    """Return reserved stock to the shelf when an order stops being fulfilled."""
    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product:
            product.stock += item.quantity


def _void_referral_earnings(order: Order, db: Session) -> None:
    """A cancelled sale never earned its referrer a commission.

    Pending earnings are rejected. An already-approved earning is also rejected
    and its wallet credit reversed, so a referrer isn't paid for a sale that
    fell through.
    """
    earnings = db.query(ReferralEarning).filter(ReferralEarning.order_id == order.id).all()
    for earning in earnings:
        if earning.status == "approved":
            referrer = db.query(User).filter(User.id == earning.referrer_user_id).first()
            if referrer:
                referrer.wallet_balance = max(0.0, referrer.wallet_balance - earning.reward_amount)
                db.add(WalletTransaction(
                    user_id=referrer.id,
                    transaction_type="debit",
                    amount=earning.reward_amount,
                    source="referral_reversal",
                    reference_id=str(order.id),
                    description="Referral commission reversed because the order was cancelled",
                ))
        earning.status = "rejected"
        earning.approved_at = None


def _perform_cancel(order: Order, db: Session, reason: str) -> str | None:
    """Cancel an order: restore stock, refund if paid, mark cancelled, notify.

    Shared by the customer cancel endpoint, the admin status flow, and the
    stale-order expiry. Returns a refund note for the caller to surface.
    """
    if order.order_status == "cancelled":
        return None
    # Local import keeps the module graph acyclic: payment_service imports
    # fulfillment_service, and fulfillment_service lazily imports this module.
    from app.services import payment_service
    order.order_status = "cancelled"
    _restore_stock(order, db)
    _void_referral_earnings(order, db)
    refund_note = None
    if order.payment_status == "paid":
        refund_note = payment_service.refund_payment(order, db)
    db.commit()
    db.refresh(order)
    try:
        notifications.notify_order_cancelled(order, reason)
    except Exception:
        pass
    return refund_note


def _order_gst_breakup(order: Order) -> dict:
    """CGST/SGST/IGST amounts stored on the order, with a legacy fallback.

    Orders placed before the split columns existed only have gst_amount; treat
    those as intra-state and split the total evenly.
    """
    cgst = order.cgst_amount or 0.0
    sgst = order.sgst_amount or 0.0
    igst = getattr(order, "igst_amount", 0.0) or 0.0
    if cgst == 0.0 and sgst == 0.0 and igst == 0.0:
        half = round((order.gst_amount or 0.0) / 2, 2)
        return {"cgst_amount": half, "sgst_amount": half, "igst_amount": 0.0}
    return {
        "cgst_amount": round(cgst, 2),
        "sgst_amount": round(sgst, 2),
        "igst_amount": round(igst, 2),
    }


def format_order(order: Order) -> dict:
    try:
        return_evidence = json.loads(order.return_evidence) if order.return_evidence else []
    except (ValueError, TypeError):
        return_evidence = []
    return {
        "id": str(order.id),
        "user_id": str(order.user_id),
        "order_number": order.order_number,
        "subtotal": order.subtotal,
        "gst_amount": order.gst_amount,
        # CGST/SGST/IGST are locked in at checkout based on place of supply.
        # Legacy orders (predating these columns) fall back to an even
        # intra-state split of the stored total.
        **_order_gst_breakup(order),
        "discount_amount": order.discount_amount,
        "delivery_fee": order.delivery_fee or 0.0,
        "final_amount": order.final_amount,
        "order_status": order.order_status,
        "payment_status": order.payment_status,
        "shipping_address": order.shipping_address,
        "shipping_state": order.shipping_state,
        "return_reason": order.return_reason,
        "return_status": order.return_status,
        "return_evidence": return_evidence,
        "return_admin_note": order.return_admin_note,
        "estimated_delivery": order.estimated_delivery,
        "dispatched_at": order.dispatched_at,
        "delivered_at": order.delivered_at,
        "return_requested_at": order.return_requested_at,
        "return_approved_at": order.return_approved_at,
        "return_picked_up_at": order.return_picked_up_at,
        "awb_code": order.awb_code,
        "courier_name": order.courier_name,
        "shipment_status": order.shipment_status,
        "tracking_url": order.tracking_url,
        "created_at": order.created_at,
        "items": [
            {
                "id": str(item.id),
                "product_id": str(item.product_id),
                "product_name": item.product_name,
                "variant_id": str(item.variant_id) if item.variant_id else None,
                "quantity": item.quantity,
                "price": item.price,
            }
            for item in order.items
        ],
    }


def request_return(user_id: str, order_id: str, req: dict, db: Session) -> dict:
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.order_status not in ("delivered",):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only delivered orders can be returned")
    order.return_reason = req.get("reason", "")
    order.return_status = "requested"
    order.return_requested_at = datetime.now(timezone.utc)
    evidence = req.get("evidence") or []
    order.return_evidence = json.dumps(evidence) if evidence else None
    db.commit()
    db.refresh(order)
    try:
        notifications.notify_return_requested(order)
    except Exception:
        pass
    return {"message": "Return request submitted", "return_status": "requested"}


def request_replace(user_id: str, order_id: str, req: dict, db: Session) -> dict:
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.order_status not in ("delivered",):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only delivered orders can be replaced")
    order.return_reason = req.get("reason", "")
    order.return_status = "replace_requested"
    order.return_requested_at = datetime.now(timezone.utc)
    evidence = req.get("evidence") or []
    order.return_evidence = json.dumps(evidence) if evidence else None
    db.commit()
    db.refresh(order)
    try:
        notifications.notify_return_requested(order)
    except Exception:
        pass
    return {"message": "Replace request submitted", "return_status": "replace_requested"}
