import random
import string
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core import gst
from app.services import delivery_service, referral_service
from app.models.cart import CartItem
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.schemas.order import OrderCreateRequest


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
        order_status="placed",
        shipping_address=req.shipping_address,
        estimated_delivery=estimated_delivery,
    )
    db.add(order)
    db.flush()

    for item_data in order_items_data:
        order_item = OrderItem(order_id=order.id, **item_data)
        db.add(order_item)

    db.flush()

    referral_service.record_first_order_referral(
        user,
        order,
        subtotal,
        order_items_data[0]["product_id"] if order_items_data else None,
        db,
    )

    db.commit()
    db.refresh(order)
    return get_order_detail(str(order.id), db)


def get_user_orders(user_id: str, db: Session):
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
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    order.order_status = status_str
    db.commit()
    db.refresh(order)
    return format_order(order)


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
        "return_reason": order.return_reason,
        "return_status": order.return_status,
        "estimated_delivery": order.estimated_delivery,
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
    db.commit()
    db.refresh(order)
    return {"message": "Return request submitted", "return_status": "requested"}


def request_replace(user_id: str, order_id: str, req: dict, db: Session) -> dict:
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.order_status not in ("delivered",):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only delivered orders can be replaced")
    order.return_reason = req.get("reason", "")
    order.return_status = "replace_requested"
    db.commit()
    db.refresh(order)
    return {"message": "Replace request submitted", "return_status": "replace_requested"}
