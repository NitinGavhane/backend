"""
Backfill ShipRocket courier orders for existing, financially-committed orders
that predate the checkout auto-sync.

Run from the backend directory:
    venv\\Scripts\\python scripts\\sync_shiprocket.py

Syncs every order that has no ShipRocket courier order yet but should: any
active status (placed / processing / dispatched / out_for_delivery) that is
either already paid (prepaid) or booked as COD. Cancelled and delivered orders
are skipped. Results are printed per order.

This is a one-off maintenance tool — new orders are pushed automatically at
checkout (COD chosen or prepaid payment verified) so this only matters for
orders placed before that hook existed.
"""

import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.core.database import SessionLocal
from app.models.order import Order
from app.models.payment import Payment
from app.services import fulfillment_service, shiprocket_service

# Import every mapped model so the ORM registry can resolve every relationship
# string — the models package is empty, so each table mapper has to be loaded
# explicitly (User -> CartItem/orders, Order -> Payment/GstInvoice, ...).
from app.models import (  # noqa: F401,E402
    address,
    banner,
    blog,
    cart,
    category,
    contact,
    coupon,
    delivery,
    order as _order_model,
    payment,
    payment_method,
    product,
    referral,
    review,
    user,
    wallet,
    wishlist,
)


def main() -> None:
    if not shiprocket_service.is_enabled():
        print("ShipRocket is not enabled / configured. Nothing to do.")
        return

    db = SessionLocal()
    try:
        cod_order_ids = (
            db.query(Payment.order_id).filter(Payment.gateway == "cod").subquery()
        )
        orders = (
            db.query(Order)
            .options(joinedload(Order.items))
            .filter(
                Order.shiprocket_order_id.is_(None),
                # Every active status — cancelled and delivered orders are
                # excluded because they must not reach the courier.
                Order.order_status.in_(
                    ["placed", "processing", "dispatched", "out_for_delivery"]
                ),
                or_(
                    Order.payment_status == "paid",
                    Order.id.in_(cod_order_ids),
                ),
            )
            .order_by(Order.created_at.asc())
            .all()
        )
        print(f"Found {len(orders)} orders to sync.\n")
        synced = skipped = failed = 0
        for order in orders:
            error = fulfillment_service.sync_order_to_shiprocket(order, db)
            if order.shiprocket_order_id:
                print(
                    f"  OK   {order.order_number} -> ShipRocket order {order.shiprocket_order_id}"
                )
                synced += 1
            elif error:
                print(f"  FAIL {order.order_number}: {error}")
                failed += 1
            else:
                print(f"  SKIP {order.order_number}")
                skipped += 1
        print(f"\nDone: {synced} synced, {failed} failed, {skipped} skipped.")
    finally:
        db.close()


if __name__ == "__main__":
    main()