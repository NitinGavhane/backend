from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_admin
from app.models.user import User
from app.schemas.order import OrderCreateRequest, OrderResponse, OrderStatusUpdate
from app.services import order_service

router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])


@router.post("", response_model=OrderResponse)
def create_order(req: OrderCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return order_service.create_order(str(user.id), req, db)


@router.get("", response_model=list[OrderResponse])
def list_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return order_service.get_user_orders(str(user.id), db)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return order_service.get_order_detail(order_id, db)


@router.put("/{order_id}/status", response_model=OrderResponse)
def update_order_status(order_id: str, req: OrderStatusUpdate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return order_service.update_order_status(order_id, req.status, db)
