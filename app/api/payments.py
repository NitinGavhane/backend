from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.payment import PaymentCreateRequest, PaymentResponse, PaymentVerifyRequest
from app.services import payment_service

router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])


@router.post("/create", response_model=PaymentResponse)
def create_payment(req: PaymentCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return payment_service.create_payment(req.order_id, db)


@router.post("/verify")
def verify_payment(req: PaymentVerifyRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return payment_service.verify_payment(req.order_id, req.transaction_id, req.payment_method, db)
