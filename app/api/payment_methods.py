from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.payment_method import PaymentMethodResponse

router = APIRouter(prefix="/api/v1/payment-methods", tags=["Payment Methods"])


@router.get("", response_model=list[PaymentMethodResponse])
def list_payment_methods(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Razorpay is the only supported payment method.
    methods = [
        {"id": "razorpay", "name": "Razorpay", "code": "razorpay", "icon_url": None, "is_active": True},
    ]
    return methods
