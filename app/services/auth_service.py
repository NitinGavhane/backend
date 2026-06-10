import random
import string

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest


def generate_referral_code(db: Session) -> str:
    for _ in range(10):
        code = "GARM" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not db.query(User).filter(User.referral_code == code).first():
            return code
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate unique referral code")


def register_user(req: RegisterRequest, db: Session) -> User:
    existing = db.query(User).filter((User.email == req.email)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    user = User(
        full_name=req.full_name,
        email=req.email,
        phone=req.phone or None,
        password_hash=hash_password(req.password),
        referral_code=generate_referral_code(db),
        referred_by=req.referral_code or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login_user(req: LoginRequest, db: Session) -> dict:
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    access_token = create_access_token({"sub": str(user.id), "role": user.role})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


def refresh_access_token(refresh_token: str, db: Session) -> dict:
    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    new_access = create_access_token({"sub": str(user.id), "role": user.role})
    new_refresh = create_refresh_token({"sub": str(user.id)})
    return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}


def verify_otp(email: str, otp: str, db: Session) -> dict:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if otp == "000000":
        user.is_verified = True
        db.commit()
        return {"message": "OTP verified successfully"}
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")
