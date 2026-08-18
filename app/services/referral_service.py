import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings as app_settings
from app.models.order import Order
from app.models.product import Product, ProductImage
from app.models.referral import ReferralEarning, ReferralSettings, ReferralShareClick
from app.models.user import User
from app.schemas.referral import ReferralSettingsUpdate


def get_settings(db: Session) -> ReferralSettings:
    """The singleton refer-and-earn settings row, created on first use."""
    settings = db.query(ReferralSettings).first()
    if not settings:
        settings = ReferralSettings(enabled=True, commission_percentage=5.0)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def update_settings(req: ReferralSettingsUpdate, db: Session) -> ReferralSettings:
    settings = get_settings(db)
    for key, value in req.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)
    if settings.commission_percentage < 0:
        settings.commission_percentage = 0.0
    db.commit()
    db.refresh(settings)
    return settings


def suggested_reward(purchase_amount: float, settings: ReferralSettings) -> float:
    """Commission the admin is offered when approving — never paid on its own."""
    return round(purchase_amount * settings.commission_percentage / 100, 2)


def get_referral_stats(user_id: str, db: Session) -> dict:
    user_uuid = uuid.UUID(user_id)
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    earnings = db.query(ReferralEarning).filter(ReferralEarning.referrer_user_id == user_uuid).all()
    total_earnings = sum(e.reward_amount for e in earnings if e.status == "approved")
    pending_earnings = sum(e.reward_amount for e in earnings if e.status == "pending")
    successful = sum(1 for e in earnings if e.status == "approved")
    pending = sum(1 for e in earnings if e.status == "pending")
    total_clicks = db.query(ReferralShareClick).filter(ReferralShareClick.referrer_user_id == user_uuid).count()
    programme = get_settings(db)
    return {
        "referral_code": user.referral_code,
        "total_earnings": round(total_earnings, 2),
        # What is waiting on the admin's approval — shown so a referrer can see
        # a reward is coming rather than wondering if the share worked.
        "pending_earnings": round(pending_earnings, 2),
        "successful_referrals": successful,
        "pending_referrals": pending,
        "total_clicks": total_clicks,
        "wallet_balance": user.wallet_balance,
        "commission_percentage": programme.commission_percentage if programme.enabled else 0.0,
        "programme_enabled": programme.enabled,
        "share_base_url": app_settings.SITE_URL,
    }


def get_referral_history(user_id: str, db: Session):
    user_uuid = uuid.UUID(user_id)
    earnings = (
        db.query(ReferralEarning)
        .options(joinedload(ReferralEarning.referrer))
        .filter(ReferralEarning.referrer_user_id == user_uuid)
        .order_by(ReferralEarning.created_at.desc())
        .all()
    )
    result = []
    for e in earnings:
        item = {
            "id": str(e.id),
            "referred_user_name": "User",
            "referred_user_email": None,
            "order_id": str(e.order_id),
            "product_id": str(e.product_id) if e.product_id else None,
            "product_name": None,
            "product_image": None,
            "purchase_amount": e.purchase_amount,
            "reward_amount": e.reward_amount,
            "reward_percentage": e.reward_percentage,
            "status": e.status,
            "created_at": e.created_at,
            "approved_at": e.approved_at,
        }
        if e.referred_user_id:
            referred = db.query(User).filter(User.id == e.referred_user_id).first()
            if referred:
                item["referred_user_name"] = referred.full_name
                item["referred_user_email"] = referred.email
        if e.product_id:
            product = db.query(Product).filter(Product.id == e.product_id).first()
            if product:
                item["product_name"] = product.title
                primary_img = (
                    db.query(ProductImage)
                    .filter(ProductImage.product_id == e.product_id, ProductImage.is_primary == True)
                    .first()
                )
                item["product_image"] = primary_img.image_url if primary_img else None
        result.append(item)
    return result


def generate_share_url(product_id: str, referral_code: str) -> str:
    """An absolute, clickable storefront link that carries the referrer's code.

    Was a bare path ("/product/<id>?ref=CODE"), which is not something a
    customer can paste into WhatsApp.
    """
    base = app_settings.SITE_URL.rstrip("/")
    return f"{base}/product/{product_id}?ref={referral_code}"


def track_share_click(product_id: str, referral_code: str, db: Session, ip_address: str = None, user_agent: str = None) -> dict:
    referrer = db.query(User).filter(User.referral_code == referral_code).first()
    if not referrer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid referral code")
    try:
        parsed_product_id = uuid.UUID(product_id) if product_id else None
    except ValueError:
        parsed_product_id = None
    click = ReferralShareClick(
        product_id=parsed_product_id,
        referrer_user_id=referrer.id,
        referral_code=referral_code,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(click)
    db.commit()
    return {"message": "Click tracked"}


def record_first_order_referral(user: User, order, subtotal: float, product_id, db: Session):
    """Record a pending commission for whoever referred `user`.

    Only the referred customer's **first** order earns — a repeat customer is no
    longer a referral. Adds the row to the caller's session without committing,
    so it lands in the same transaction as the order.

    The commission base is the product subtotal, not the order total: the
    referrer is not paid a share of GST or the delivery charge.
    """
    if not user.referred_by:
        return
    programme = get_settings(db)
    if not programme.enabled:
        return
    referrer = db.query(User).filter(User.referral_code == user.referred_by).first()
    # A code that no longer exists, or someone's own code, earns nothing.
    if not referrer or referrer.id == user.id:
        return
    # First *paid* order only. The new order is already flushed, so look for any
    # other financially-committed order — an awaiting-payment or cancelled order
    # that was never paid does not consume the referral.
    previous_orders = (
        db.query(Order)
        .filter(
            Order.user_id == user.id,
            Order.id != order.id,
            Order.order_status != "pending_payment",
            Order.order_status != "cancelled",
        )
        .count()
    )
    if previous_orders:
        return
    # Belt and braces: never record two earnings for the same referred customer.
    # A rejected earning (e.g. because that order was cancelled) is not a real
    # referral — it must not block the next order from earning.
    already = (
        db.query(ReferralEarning)
        .filter(
            ReferralEarning.referred_user_id == user.id,
            ReferralEarning.status != "rejected",
        )
        .count()
    )
    if already:
        return
    db.add(ReferralEarning(
        referrer_user_id=referrer.id,
        referred_user_id=user.id,
        order_id=order.id,
        product_id=product_id,
        referral_code=user.referred_by,
        purchase_amount=round(subtotal, 2),
        # Suggested payout, shown to the admin and to the referrer as "pending".
        # Nothing reaches a wallet until the admin approves it.
        reward_amount=suggested_reward(subtotal, programme),
        reward_percentage=programme.commission_percentage,
        status="pending",
    ))


def get_admin_referral_purchases(db: Session, status_filter: str = None):
    query = db.query(ReferralEarning).order_by(ReferralEarning.created_at.desc())
    if status_filter:
        query = query.filter(ReferralEarning.status == status_filter)
    earnings = query.all()
    result = []
    for e in earnings:
        referrer = db.query(User).filter(User.id == e.referrer_user_id).first()
        referred = db.query(User).filter(User.id == e.referred_user_id).first() if e.referred_user_id else None
        order = db.query(Order).filter(Order.id == e.order_id).first()
        product_name = None
        if e.product_id:
            product = db.query(Product).filter(Product.id == e.product_id).first()
            if product:
                product_name = product.title
        item = {
            "id": str(e.id),
            "referrer_name": referrer.full_name if referrer else "Unknown",
            "referrer_email": referrer.email if referrer else "",
            "referrer_code": e.referral_code,
            "referred_user_name": referred.full_name if referred else None,
            "referred_user_email": referred.email if referred else None,
            "product_id": str(e.product_id) if e.product_id else None,
            "product_name": product_name,
            "order_id": str(e.order_id),
            "order_number": order.order_number if order else None,
            "purchase_amount": e.purchase_amount,
            "reward_amount": e.reward_amount,
            "reward_percentage": e.reward_percentage,
            "status": e.status,
            "created_at": e.created_at,
        }
        result.append(item)
    return result


def approve_referral_reward(earning_id: str, reward_percentage: float, reward_amount: float | None, db: Session):
    earning = db.query(ReferralEarning).filter(ReferralEarning.id == uuid.UUID(earning_id)).first()
    if not earning:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral earning not found")
    if earning.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reward is not in pending status")

    amount = reward_amount if reward_amount else round(earning.purchase_amount * reward_percentage / 100, 2)
    earning.reward_percentage = reward_percentage
    earning.reward_amount = amount
    earning.status = "approved"
    earning.approved_at = datetime.now(timezone.utc)

    referrer = db.query(User).filter(User.id == earning.referrer_user_id).first()
    if referrer:
        referrer.wallet_balance += amount
        from app.models.wallet import WalletTransaction
        wallet_txn = WalletTransaction(
            user_id=referrer.id,
            transaction_type="credit",
            amount=amount,
            source="referral_commission",
            reference_id=str(earning.order_id),
            description="Referral reward approved for order",
        )
        db.add(wallet_txn)

    db.commit()
    return {"message": "Reward approved", "amount": amount}


def reject_referral_reward(earning_id: str, db: Session):
    earning = db.query(ReferralEarning).filter(ReferralEarning.id == uuid.UUID(earning_id)).first()
    if not earning:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral earning not found")
    if earning.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reward is not in pending status")
    earning.status = "rejected"
    db.commit()
    return {"message": "Reward rejected"}


def get_product_referral_report(db: Session):
    products = db.query(Product).all()
    report = []
    for product in products:
        clicks = db.query(ReferralShareClick).filter(ReferralShareClick.product_id == product.id).count()
        purchases = db.query(ReferralEarning).filter(ReferralEarning.product_id == product.id, ReferralEarning.status == "approved").count()
        total_revenue = db.query(ReferralEarning).filter(ReferralEarning.product_id == product.id, ReferralEarning.status == "approved").with_entities(ReferralEarning.purchase_amount).all()
        total = sum(r[0] for r in total_revenue if r[0])
        report.append({
            "product_id": str(product.id),
            "product_name": product.title,
            "total_clicks": clicks,
            "total_purchases": purchases,
            "total_revenue": round(total, 2),
        })
    return report


def get_user_referral_report(db: Session):
    users = db.query(User).filter(User.role == "customer").all()
    report = []
    for user in users:
        shares = db.query(ReferralShareClick).filter(ReferralShareClick.referrer_user_id == user.id).count()
        clicks = db.query(ReferralShareClick).filter(ReferralShareClick.referrer_user_id == user.id).count()
        purchases = db.query(ReferralEarning).filter(ReferralEarning.referrer_user_id == user.id, ReferralEarning.status == "approved").count()
        earnings = db.query(ReferralEarning).filter(ReferralEarning.referrer_user_id == user.id, ReferralEarning.status == "approved").with_entities(ReferralEarning.reward_amount).all()
        total_earned = sum(r[0] for r in earnings if r[0])
        pending = db.query(ReferralEarning).filter(ReferralEarning.referrer_user_id == user.id, ReferralEarning.status == "pending").with_entities(ReferralEarning.reward_amount).all()
        total_pending = sum(r[0] for r in pending if r[0])
        report.append({
            "user_id": str(user.id),
            "user_name": user.full_name,
            "user_email": user.email,
            "total_shares": shares,
            "total_clicks": clicks,
            "total_purchases": purchases,
            "total_earnings": round(total_earned, 2),
            "pending_rewards": round(total_pending, 2),
        })
    return report
