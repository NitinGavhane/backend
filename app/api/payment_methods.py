from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.payment_method import PaymentMethod
from app.models.user import User
from app.schemas.payment_method import PaymentMethodResponse

router = APIRouter(prefix="/api/v1/payment-methods", tags=["Payment Methods"])

DEFAULT_REGION = "IN"


@router.get("", response_model=list[PaymentMethodResponse])
def list_payment_methods(
    region: str = DEFAULT_REGION,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Active payment methods offered in `region` (an alpha-2 country code).

    The client passes the country of the delivery address it is checking out to.
    """
    methods = (
        db.query(PaymentMethod)
        .filter(PaymentMethod.is_active == True)  # noqa: E712
        .order_by(PaymentMethod.sort_order.asc(), PaymentMethod.name.asc())
        .all()
    )
    return [
        {
            "id": str(m.id),
            "name": m.name,
            "code": m.code,
            "description": m.description,
            "icon_url": m.icon_url,
            "is_active": m.is_active,
        }
        for m in methods
        if m.available_in(region)
    ]
