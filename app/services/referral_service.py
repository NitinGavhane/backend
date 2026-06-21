import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.order import Order
from app.models.product import Product, ProductImage
from app.models.referral import ReferralEarning, ReferralShareClick
from app.models.user import User


def get_referral_stats(user_id: str, db: Session) -> dict:
    user_uuid = uuid.UUID(user_id)
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    earnings = db.query(ReferralEarning).filter(ReferralEarning.referrer_user_id == user_uuid).all()
    total_earnings = sum(e.reward_amount for e in earnings if e.status == "approved")
    successful = sum(1 for e in earnings if e.status == "approved")
    pending = sum(1 for e in earnings if e.status == "pending")
    total_clicks = db.query(ReferralShareClick).filter(ReferralShareClick.referrer_user_id == user_uuid).count()
    return {
        "referral_code": user.referral_code,
        "total_earnings": round(total_earnings, 2),
        "successful_referrals": successful,
        "pending_referrals": pending,
        "total_clicks": total_clicks,
        "wallet_balance": user.wallet_balance,
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
    return f"/product/{product_id}?ref={referral_code}"


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


def record_referral_purchase(
    referred_user_id: str,
    referred_by_code: str,
    order_id: str,
    product_id: str,
    purchase_amount: float,
    db: Session,
):
    referrer = db.query(User).filter(User.referral_code == referred_by_code).first()
    if not referrer:
        return
    earning = ReferralEarning(
        referrer_user_id=referrer.id,
        referred_user_id=uuid.UUID(referred_user_id),
        order_id=uuid.UUID(order_id),
        product_id=uuid.UUID(product_id) if product_id else None,
        referral_code=referred_by_code,
        purchase_amount=purchase_amount,
        reward_amount=0.0,
        reward_percentage=0.0,
        status="pending",
    )
    db.add(earning)
    db.commit()


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
