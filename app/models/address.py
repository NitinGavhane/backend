import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Address(Base):
    __tablename__ = "addresses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    street = Column(String(500), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    pincode = Column(String(20), nullable=False)
    is_default = Column(Boolean, default=False)
    type = Column(String(50), default="Home")

    user = relationship("User", backref="addresses")

    def to_dict(self):
        return {
            "id": self.id,
            "fullName": self.full_name,
            "phone": self.phone,
            "street": self.street,
            "city": self.city,
            "state": self.state,
            "pincode": self.pincode,
            "isDefault": self.is_default,
            "type": self.type,
        }
