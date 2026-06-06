from datetime import datetime

from pydantic import BaseModel


class AdminUserResponse(BaseModel):
    id: str
    full_name: str
    email: str
    phone: str | None = None
    role: str
    referral_code: str | None = None
    wallet_balance: float
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AdminDashboardStats(BaseModel):
    total_users: int = 0
    total_products: int = 0
    total_orders: int = 0
    total_revenue: float = 0.0
    pending_orders: int = 0


class SalesReportResponse(BaseModel):
    date: str
    total_orders: int
    total_revenue: float
    total_gst: float
