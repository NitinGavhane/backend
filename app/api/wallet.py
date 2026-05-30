from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.wallet import AddMoneyRequest
from app.services import wallet_service

router = APIRouter(prefix="/api/wallet", tags=["Wallet"])


@router.get("")
def get_wallet(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return wallet_service.get_wallet(db, current_user.id)


@router.post("/add-money")
def add_money(
    req: AddMoneyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return wallet_service.add_money(db, current_user.id, req.amount, req.description)
