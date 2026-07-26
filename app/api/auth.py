from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    GoogleLoginRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserProfileResponse,
    VerifyOtpRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def _user_to_response(user: User) -> dict:
    return {
        "id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "avatar_url": user.avatar_url if hasattr(user, "avatar_url") else None,
        "role": user.role,
        "referral_code": user.referral_code,
        "wallet_balance": user.wallet_balance,
        "is_verified": user.is_verified,
    }


@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    return auth_service.register_user(req, db)


@router.post("/verify-otp")
def verify_otp(req: VerifyOtpRequest, db: Session = Depends(get_db)):
    return auth_service.verify_otp(req.email, req.otp, db)


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login_user(req, db)


@router.post("/google")
def google_login(req: GoogleLoginRequest, db: Session = Depends(get_db)):
    return auth_service.google_login(req.id_token, db)


@router.post("/refresh-token", response_model=TokenResponse)
def refresh_token(req: RefreshTokenRequest, db: Session = Depends(get_db)):
    return auth_service.refresh_access_token(req.refresh_token, db)


@router.get("/me", response_model=UserProfileResponse)
def get_profile(user: User = Depends(get_current_user)):
    return _user_to_response(user)


@router.put("/me", response_model=UserProfileResponse)
def update_profile(req: UpdateProfileRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    updated = auth_service.update_profile(user, req, db)
    return _user_to_response(updated)


@router.post("/send-login-otp")
def send_login_otp(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    return auth_service.send_login_otp(req.email, db)


@router.post("/login-with-otp")
def login_with_otp(req: VerifyOtpRequest, db: Session = Depends(get_db)):
    return auth_service.login_with_otp(req.email, req.otp, db)


@router.post("/resend-otp")
def resend_otp(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    return auth_service.resend_otp(req.email, db)


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    return auth_service.forgot_password(req.email, db)


@router.post("/change-password")
def change_password(req: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return auth_service.change_password(user, req, db)


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    return auth_service.reset_password(req, db)
