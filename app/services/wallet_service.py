import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import User
from app.models.wallet import WalletTransaction


def get_wallet(db: Session, user_id: str) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    transactions = db.query(WalletTransaction).filter(
        WalletTransaction.user_id == user_id
    ).order_by(WalletTransaction.created_at.desc()).all()

    return {
        "balance": user.wallet_balance,
        "transactions": [t.to_dict() for t in transactions],
    }


def add_money(db: Session, user_id: str, amount: float, description: str = "") -> dict:
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be positive")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.wallet_balance += amount

    transaction = WalletTransaction(
        id=str(uuid.uuid4()),
        user_id=user_id,
        amount=amount,
        type="credit",
        description=description or "Money added to wallet",
        created_at=datetime.now(timezone.utc),
    )
    db.add(transaction)
    db.commit()

    return {
        "balance": user.wallet_balance,
        "transaction": transaction.to_dict(),
    }
