from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.order import CreateOrderRequest, CreateReturnReplaceRequest
from app.services import order_service

router = APIRouter(prefix="/api/orders", tags=["Orders"])


@router.get("")
def list_orders(
    status: str = Query("all"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    orders = order_service.get_orders(db, current_user.id, status)
    return {"orders": orders}


@router.get("/{order_id}")
def get_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = order_service.get_order(db, current_user.id, order_id)
    return order.to_dict()


@router.post("")
def create_order(
    req: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items_data = [item.model_dump() for item in req.items]
    return order_service.create_order(
        db, current_user.id, items_data, req.addressId, req.paymentMethod
    )


@router.post("/{order_id}/return-replace")
def create_return_replace(
    order_id: str,
    req: CreateReturnReplaceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items_data = [item.model_dump() for item in req.items]
    return order_service.create_return_replace_request(
        db, current_user.id, order_id, req.type, items_data, req.reason
    )
