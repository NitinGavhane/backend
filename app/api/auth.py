from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshTokenRequest, RegisterRequest, TokenResponse, UserProfileResponse, VerifyOtpRequest
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/register", response_model=UserProfileResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    user = auth_service.register_user(req, db)
    return {
        "id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
        "referral_code": user.referral_code,
        "wallet_balance": user.wallet_balance,
        "is_verified": user.is_verified,
    }


@router.post("/verify-otp")
def verify_otp(req: VerifyOtpRequest, db: Session = Depends(get_db)):
    return auth_service.verify_otp(req.email, req.otp, db)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login_user(req, db)


@router.post("/refresh-token", response_model=TokenResponse)
def refresh_token(req: RefreshTokenRequest, db: Session = Depends(get_db)):
    return auth_service.refresh_access_token(req.refresh_token, db)


@router.get("/me", response_model=UserProfileResponse)
def get_profile(user: User = Depends(get_current_user)):
    return {
        "id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
        "referral_code": user.referral_code,
        "wallet_balance": user.wallet_balance,
        "is_verified": user.is_verified,
    }
