from sqlalchemy.orm import Session, joinedload

from app.models.referral import ReferralEarning
from app.models.user import User


def get_referral_stats(user_id: str, db: Session) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    earnings = db.query(ReferralEarning).filter(ReferralEarning.referrer_user_id == user_id).all()
    total_earnings = sum(e.commission_amount for e in earnings if e.status == "credited")
    successful = sum(1 for e in earnings if e.status == "credited")
    return {
        "referral_code": user.referral_code,
        "total_earnings": round(total_earnings, 2),
        "successful_referrals": successful,
        "wallet_balance": user.wallet_balance,
    }


def get_referral_history(user_id: str, db: Session):
    earnings = db.query(ReferralEarning).options(joinedload(ReferralEarning.referrer)).filter(ReferralEarning.referrer_user_id == user_id).order_by(ReferralEarning.created_at.desc()).all()
    return [
        {
            "id": str(e.id),
            "referred_user_name": "User",
            "order_id": str(e.order_id),
            "commission_amount": e.commission_amount,
            "status": e.status,
            "created_at": e.created_at,
        }
        for e in earnings
    ]
