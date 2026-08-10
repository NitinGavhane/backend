from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models.user import User
from app.services import fulfillment_service

router = APIRouter(prefix="/api/v1/admin", tags=["Fulfillment"])


class OtpRequest(BaseModel):
    otp: str


class RejectReturnRequest(BaseModel):
    reason: str


@router.get("/delivery")
def list_delivery(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return fulfillment_service.list_delivery_orders(db)


@router.post("/delivery/{order_id}/dispatch")
def dispatch(order_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return fulfillment_service.dispatch_order(order_id, db)


@router.post("/delivery/{order_id}/verify")
def verify_delivery(order_id: str, req: OtpRequest, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return fulfillment_service.verify_delivery_otp(order_id, req.otp.strip(), db)


@router.get("/delivery/{order_id}/tracking")
def delivery_tracking(order_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return fulfillment_service.get_tracking(order_id, db)


@router.get("/returns")
def list_returns(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return fulfillment_service.list_return_orders(db)


@router.post("/returns/{order_id}/approve")
def approve_return(order_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return fulfillment_service.approve_return(order_id, db)


@router.post("/returns/{order_id}/reject")
def reject_return(order_id: str, req: RejectReturnRequest, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return fulfillment_service.reject_return(order_id, req.reason, db)


@router.post("/returns/{order_id}/pickup")
def verify_return_pickup(order_id: str, req: OtpRequest, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return fulfillment_service.verify_return_pickup(order_id, req.otp.strip(), db)
