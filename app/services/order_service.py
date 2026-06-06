import random
import string
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.cart import CartItem
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.referral import ReferralEarning
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.schemas.order import OrderCreateRequest


def generate_order_number() -> str:
    return "ORD-" + datetime.now().strftime("%Y%m%d") + "-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def create_order(user_id: str, req: OrderCreateRequest, db: Session):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    subtotal = 0.0
    total_gst = 0.0
    order_items_data = []

    for item_input in req.items:
        product = db.query(Product).filter(Product.id == item_input.product_id, Product.is_active == True).first()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {item_input.product_id} not found")
        if product.stock < item_input.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Insufficient stock for {product.title}")
        unit_price = product.discount_price or product.price
        item_subtotal = unit_price * item_input.quantity
        item_gst = item_subtotal * (product.gst_percentage / 100)
        subtotal += item_subtotal
        total_gst += item_gst
        order_items_data.append({
            "product_id": product.id,
            "variant_id": item_input.variant_id,
            "product_name": product.title,
            "quantity": item_input.quantity,
            "price": unit_price,
        })
        product.stock -= item_input.quantity

    final_amount = subtotal + total_gst
    estimated_delivery = datetime.now(timezone.utc) + timedelta(days=7)

    order = Order(
        user_id=user_id,
        order_number=generate_order_number(),
        subtotal=round(subtotal, 2),
        gst_amount=round(total_gst, 2),
        discount_amount=0.0,
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

    if user.referred_by:
        referrer = db.query(User).filter(User.referral_code == user.referred_by).first()
        if referrer:
            commission = round(final_amount * 0.05, 2)
            earning = ReferralEarning(
                referrer_user_id=referrer.id,
                referred_user_id=user.id,
                order_id=order.id,
                referral_code=user.referred_by,
                commission_amount=commission,
                status="credited",
            )
            db.add(earning)
            referrer.wallet_balance += commission
            wallet_txn = WalletTransaction(
                user_id=referrer.id,
                transaction_type="credit",
                amount=commission,
                source="referral_commission",
                reference_id=str(order.id),
                description=f"Referral commission for order {order.order_number}",
            )
            db.add(wallet_txn)

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


def format_order(order: Order) -> dict:
    return {
        "id": str(order.id),
        "user_id": str(order.user_id),
        "order_number": order.order_number,
        "subtotal": order.subtotal,
        "gst_amount": order.gst_amount,
        "discount_amount": order.discount_amount,
        "final_amount": order.final_amount,
        "order_status": order.order_status,
        "payment_status": order.payment_status,
        "shipping_address": order.shipping_address,
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
