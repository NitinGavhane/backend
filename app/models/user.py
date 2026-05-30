import uuid
from sqlalchemy import Column, String, Float, Boolean, Enum as SAEnum
from app.core.database import Base
import enum


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    avatar_url = Column(String(500), nullable=True)
    wallet_balance = Column(Float, default=0.0)
    referral_code = Column(String(50), unique=True, nullable=True)
    is_verified = Column(Boolean, default=False)
    role = Column(SAEnum(UserRole), default=UserRole.user)
    created_at = Column(String(50), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "fullName": self.full_name,
            "email": self.email,
            "phone": self.phone or "",
            "avatarUrl": self.avatar_url,
            "walletBalance": self.wallet_balance,
            "referralCode": self.referral_code or "",
            "isVerified": self.is_verified,
            "role": self.role.value if self.role else "user",
        }
