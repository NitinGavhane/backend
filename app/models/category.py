import uuid
from sqlalchemy import Column, String, Integer
from app.core.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True)
    icon = Column(String(100), nullable=True)
    color = Column(String(50), nullable=True)
    product_count = Column(Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "icon": self.icon or "checkroom",
            "color": self.color or "#1A1A2E",
            "productCount": self.product_count,
        }
