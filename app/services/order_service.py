import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.order import (
    Order, OrderItem, OrderStatus,
    ReturnReplaceRequest, ReturnReplaceRequestItem,
    ReturnReplaceType, ReturnReplaceStatus,
)
from app.models.product import Product
from app.models.address import Address
from app.models.cart import CartItem


def generate_order_number() -> str:
    now = datetime.now(timezone.utc)
    return f"ORD-{now.year}-{now.month:02d}{now.day:02d}{uuid.uuid4().hex[:4].upper()}"


def get_orders(db: Session, user_id: str, status_filter: str = "all") -> list:
    query = db.query(Order).filter(Order.user_id == user_id)
    if status_filter != "all":
        query = query.filter(Order.status == status_filter)
    query = query.order_by(Order.created_at.desc())
    return [o.to_dict() for o in query.all()]


def get_order(db: Session, user_id: str, order_id: str) -> Order:
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


def create_order(db: Session, user_id: str, items_data: list, address_id: str, payment_method: str) -> dict:
    address = db.query(Address).filter(Address.id == address_id, Address.user_id == user_id).first()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")

    order = Order(
        id=str(uuid.uuid4()),
        user_id=user_id,
        order_number=generate_order_number(),
        status=OrderStatus.placed,
        address_id=address_id,
        payment_method=payment_method,
        estimated_delivery=datetime.now(timezone.utc) + timedelta(days=5),
    )

    subtotal = 0.0
    order_items = []
    for item_data in items_data:
        product = db.query(Product).filter(Product.id == item_data["productId"]).first()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {item_data['productId']} not found")
        if product.stock < item_data["quantity"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Insufficient stock for {product.title}")

        price = product.price
        subtotal += price * item_data["quantity"]
        product.stock -= item_data["quantity"]

        order_item = OrderItem(
            id=str(uuid.uuid4()),
            product_id=item_data["productId"],
            quantity=item_data["quantity"],
            price=price,
            size=item_data["size"],
            color=item_data["color"],
        )
        order_items.append(order_item)

    discount = round(subtotal * 0.05, 2) if subtotal > 100 else 0
    shipping = 0 if subtotal > 50 else 9.99
    gst = round(subtotal * 0.12, 2)
    total = round(subtotal + shipping + gst - discount, 2)

    order.subtotal = round(subtotal, 2)
    order.shipping = shipping
    order.discount = discount
    order.gst = gst
    order.total = total
    order.items = order_items

    db.add(order)
    db.commit()
    db.refresh(order)

    db.query(CartItem).filter(CartItem.user_id == user_id).delete()
    db.commit()

    return order.to_dict()


def create_return_replace_request(
    db: Session,
    user_id: str,
    order_id: str,
    req_type: str,
    items_data: list,
    reason: str,
) -> dict:
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status != OrderStatus.delivered:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Return/replace only eligible for delivered orders")

    rr_type = ReturnReplaceType.return_request if req_type == "returnRequest" else ReturnReplaceType.replace_request

    request = ReturnReplaceRequest(
        id=str(uuid.uuid4()),
        order_id=order_id,
        type=rr_type,
        status=ReturnReplaceStatus.submitted,
        reason=reason,
        created_at=datetime.now(timezone.utc),
    )

    request_items = []
    for item_data in items_data:
        rr_item = ReturnReplaceRequestItem(
            id=str(uuid.uuid4()),
            order_item_id=item_data["orderItemId"],
            quantity=item_data["quantity"],
        )
        request_items.append(rr_item)

    request.items = request_items
    db.add(request)
    db.commit()
    db.refresh(request)

    return request.to_dict()
