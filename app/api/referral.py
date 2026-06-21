from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.referral import (
    ReferralHistoryResponse,
    ReferralStatsResponse,
    ShareLinkRequest,
    ShareLinkResponse,
    TrackClickRequest,
    TrackClickResponse,
)
from app.services import referral_service

router = APIRouter(prefix="/api/v1/referral", tags=["Referral"])


@router.get("/me", response_model=ReferralStatsResponse)
def get_referral_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return referral_service.get_referral_stats(str(user.id), db)


@router.get("/history", response_model=list[ReferralHistoryResponse])
def get_referral_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return referral_service.get_referral_history(str(user.id), db)


@router.post("/share-link", response_model=ShareLinkResponse)
def generate_share_link(req: ShareLinkRequest):
    url = referral_service.generate_share_url(req.product_id, req.referral_code)
    return {"share_url": url}


@router.post("/track-click", response_model=TrackClickResponse)
def track_share_click(req: TrackClickRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return referral_service.track_share_click(req.product_id, req.referral_code, db, ip, ua)
