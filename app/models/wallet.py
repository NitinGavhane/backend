import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(String(50), nullable=False)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", backref="wallet_transactions")

    def to_dict(self):
        return {
            "id": self.id,
            "amount": self.amount,
            "type": self.type,
            "description": self.description or "",
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
