from datetime import datetime

from pydantic import BaseModel


class ReferralStatsResponse(BaseModel):
    referral_code: str | None = None
    total_earnings: float = 0.0
    successful_referrals: int = 0
    wallet_balance: float = 0.0


class ReferralHistoryResponse(BaseModel):
    id: str
    referred_user_name: str | None = None
    order_id: str
    commission_amount: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
