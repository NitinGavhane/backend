import uuid
from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    rating = Column(Float, nullable=False)
    comment = Column(String(2000), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User")
    product = relationship("Product")

    def to_dict(self):
        user = self.user
        return {
            "id": self.id,
            "productId": self.product_id,
            "userName": user.full_name if user else "Unknown",
            "rating": self.rating,
            "comment": self.comment or "",
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
