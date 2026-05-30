from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, ForgotPasswordRequest, RefreshTokenRequest
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login_user(db, req.email, req.password)


@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    return auth_service.register_user(db, req.fullName, req.email, req.phone, req.password)


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    return auth_service.forgot_password(db, req.email)


@router.post("/refresh")
def refresh_token(req: RefreshTokenRequest, db: Session = Depends(get_db)):
    return auth_service.refresh_access_token(db, req.refreshToken)
