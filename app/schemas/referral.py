from datetime import datetime

from pydantic import BaseModel


class ReferralStatsResponse(BaseModel):
    referral_code: str | None = None
    total_earnings: float = 0.0
    successful_referrals: int = 0
    pending_referrals: int = 0
    total_clicks: int = 0
    wallet_balance: float = 0.0


class ReferralHistoryResponse(BaseModel):
    id: str
    referred_user_name: str | None = None
    referred_user_email: str | None = None
    order_id: str
    product_id: str | None = None
    product_name: str | None = None
    product_image: str | None = None
    purchase_amount: float = 0.0
    reward_amount: float = 0.0
    reward_percentage: float = 0.0
    status: str
    created_at: datetime
    approved_at: datetime | None = None

    class Config:
        from_attributes = True


class ShareLinkRequest(BaseModel):
    product_id: str
    referral_code: str


class ShareLinkResponse(BaseModel):
    share_url: str


class TrackClickRequest(BaseModel):
    product_id: str
    referral_code: str
    ip_address: str | None = None
    user_agent: str | None = None


class TrackClickResponse(BaseModel):
    message: str


class AdminReferralPurchaseResponse(BaseModel):
    id: str
    referrer_name: str
    referrer_email: str
    referrer_code: str | None = None
    referred_user_name: str | None = None
    referred_user_email: str | None = None
    product_id: str | None = None
    product_name: str | None = None
    order_id: str
    order_number: str | None = None
    purchase_amount: float
    reward_amount: float
    reward_percentage: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ApproveRewardRequest(BaseModel):
    reward_percentage: float
    reward_amount: float | None = None


class ReferralProductReport(BaseModel):
    product_id: str
    product_name: str
    total_clicks: int
    total_purchases: int
    total_revenue: float


class ReferralUserReport(BaseModel):
    user_id: str
    user_name: str
    user_email: str
    total_shares: int
    total_clicks: int
    total_purchases: int
    total_earnings: float
    pending_rewards: float
