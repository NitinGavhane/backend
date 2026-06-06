from sqlalchemy.orm import Session

from app.models.user import User
from app.models.wallet import WalletTransaction


def get_wallet_balance(user_id: str, db: Session) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    return {"balance": user.wallet_balance}


def get_wallet_transactions(user_id: str, db: Session):
    transactions = db.query(WalletTransaction).filter(WalletTransaction.user_id == user_id).order_by(WalletTransaction.created_at.desc()).all()
    return [
        {
            "id": str(t.id),
            "transaction_type": t.transaction_type,
            "amount": t.amount,
            "source": t.source,
            "reference_id": t.reference_id,
            "description": t.description,
            "created_at": t.created_at,
        }
        for t in transactions
    ]
