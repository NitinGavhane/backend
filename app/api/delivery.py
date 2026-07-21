from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.delivery import DeliverySettingsResponse
from app.services import delivery_service

router = APIRouter(prefix="/api/v1/delivery", tags=["Delivery"])


@router.get("", response_model=DeliverySettingsResponse)
def get_delivery_settings(db: Session = Depends(get_db)):
    """Public delivery policy the checkout uses to show the fee before an
    order is placed."""
    return delivery_service.get_settings(db)
