import uuid
from sqlalchemy import Column, String, Float, Integer, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    description = Column(String(2000), nullable=True)
    brand = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True)
    category_id = Column(String, ForeignKey("categories.id"), nullable=True)
    price = Column(Float, nullable=False)
    original_price = Column(Float, nullable=False)
    rating = Column(Float, default=4.5)
    review_count = Column(Integer, default=0)
    discount_percentage = Column(Integer, default=0)
    sizes = Column(JSON, default=list)
    colors = Column(JSON, default=list)
    is_featured = Column(Boolean, default=False)
    is_new = Column(Boolean, default=False)
    badge = Column(String(100), default="")
    stock = Column(Integer, default=50)
    image_url = Column(String(500), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description or "",
            "brand": self.brand or "",
            "category": self.category or "",
            "categoryId": self.category_id or "",
            "price": self.price,
            "originalPrice": self.original_price,
            "rating": self.rating,
            "reviewCount": self.review_count,
            "discountPercentage": self.discount_percentage,
            "sizes": self.sizes or [],
            "colors": self.colors or [],
            "isFeatured": self.is_featured,
            "isNew": self.is_new,
            "badge": self.badge or "",
            "stock": self.stock,
            "imageUrl": self.image_url,
        }
