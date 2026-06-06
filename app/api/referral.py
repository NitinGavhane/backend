from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.referral import ReferralHistoryResponse, ReferralStatsResponse
from app.services import referral_service

router = APIRouter(prefix="/api/v1/referral", tags=["Referral"])


@router.get("/me", response_model=ReferralStatsResponse)
def get_referral_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return referral_service.get_referral_stats(str(user.id), db)


@router.get("/history", response_model=list[ReferralHistoryResponse])
def get_referral_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return referral_service.get_referral_history(str(user.id), db)
