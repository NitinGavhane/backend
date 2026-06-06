from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.wallet import WalletBalanceResponse, WalletTransactionResponse
from app.services import wallet_service

router = APIRouter(prefix="/api/v1/wallet", tags=["Wallet"])


@router.get("/balance", response_model=WalletBalanceResponse)
def get_balance(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return wallet_service.get_wallet_balance(str(user.id), db)


@router.get("/transactions", response_model=list[WalletTransactionResponse])
def get_transactions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return wallet_service.get_wallet_transactions(str(user.id), db)
