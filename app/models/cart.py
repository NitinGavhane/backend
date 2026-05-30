import uuid
from sqlalchemy import Column, String, Integer, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1)
    selected_size = Column(String(50), nullable=False)
    selected_color = Column(String(100), nullable=False)

    user = relationship("User", backref="cart_items")
    product = relationship("Product")

    def to_dict(self):
        return {
            "id": self.id,
            "product": self.product.to_dict() if self.product else None,
            "quantity": self.quantity,
            "selectedSize": self.selected_size,
            "selectedColor": self.selected_color,
            "totalPrice": round((self.product.price if self.product else 0) * self.quantity, 2),
        }
