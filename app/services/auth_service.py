import random
import re
import string
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RegisterRequest, ResetPasswordRequest, UpdateProfileRequest
from app.services.email_service import send_otp_email, send_password_reset_email


def generate_referral_code(db: Session, full_name: str = "") -> str:
    clean = re.sub(r'[^A-Z]', '', full_name.upper())
    prefix = clean[:4]
    suffix_len = 10 - len(prefix)
    for _ in range(10):
        code = prefix + "".join(random.choices(string.ascii_uppercase + string.digits, k=suffix_len))
        if not db.query(User).filter(User.referral_code == code).first():
            return code
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate unique referral code")


def _generate_otp() -> str:
    return f"{random.randint(0, 999999):06d}"


def _send_and_store_otp(user: User, db: Session, email_type: str = "verification") -> dict:
    otp = _generate_otp()
    user.otp_code = otp
    user.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.commit()

    if email_type == "verification":
        send_otp_email(user.email, otp)
    else:
        send_password_reset_email(user.email, otp)

    return {"message": f"OTP sent to {user.email}"}


def _verify_otp_code(user: User, otp: str, db: Session) -> None:
    if user.otp_code is None or user.otp_expires_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No OTP requested")
    if datetime.now(timezone.utc) > user.otp_expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP has expired")
    if user.otp_code != otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")

    user.otp_code = None
    user.otp_expires_at = None
    db.commit()


def register_user(req: RegisterRequest, db: Session) -> dict:
    existing = db.query(User).filter((User.email == req.email)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    if req.phone:
        existing_phone = db.query(User).filter(User.phone == req.phone).first()
        if existing_phone:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone already registered")
    user = User(
        full_name=req.full_name,
        email=req.email,
        phone=req.phone or None,
        password_hash=hash_password(req.password),
        referral_code=generate_referral_code(db, req.full_name),
        referred_by=req.referral_code or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    otp = _generate_otp()
    user.otp_code = otp
    user.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.commit()

    send_otp_email(user.email, otp)

    return {
        "user": {
            "id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "avatar_url": user.avatar_url if hasattr(user, "avatar_url") else None,
            "role": user.role,
            "referral_code": user.referral_code,
            "wallet_balance": user.wallet_balance,
            "is_verified": user.is_verified,
        },
        "message": "Registration successful. Please verify your email with the OTP sent.",
    }


def verify_otp(email: str, otp: str, db: Session) -> dict:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    _verify_otp_code(user, otp, db)
    user.is_verified = True
    db.commit()

    access_token = create_access_token({"sub": str(user.id), "role": user.role})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return {
        "message": "Email verified successfully",
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


def forgot_password(email: str, db: Session) -> dict:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    otp = _generate_otp()
    user.otp_code = otp
    user.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.commit()

    send_password_reset_email(user.email, otp)

    return {"message": f"Password reset OTP sent to {user.email}"}


def reset_password(req: ResetPasswordRequest, db: Session) -> dict:
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    _verify_otp_code(user, req.otp, db)
    user.password_hash = hash_password(req.new_password)
    db.commit()

    return {"message": "Password reset successfully"}


def send_login_otp(email: str, db: Session) -> dict:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No account found with this email")

    otp = _generate_otp()
    user.otp_code = otp
    user.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.commit()

    send_otp_email(user.email, otp)

    return {"message": f"Login OTP sent to {user.email}"}


def login_with_otp(email: str, otp: str, db: Session) -> dict:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No account found with this email")

    _verify_otp_code(user, otp, db)

    access_token = create_access_token({"sub": str(user.id), "role": user.role})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return {
        "user": {
            "id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "avatar_url": user.avatar_url if hasattr(user, "avatar_url") else None,
            "role": user.role,
            "referral_code": user.referral_code,
            "wallet_balance": user.wallet_balance,
            "is_verified": user.is_verified,
        },
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


def resend_otp(email: str, db: Session) -> dict:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    otp = _generate_otp()
    user.otp_code = otp
    user.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.commit()

    send_otp_email(user.email, otp)

    return {"message": f"OTP resent to {user.email}"}


def login_user(req: LoginRequest, db: Session) -> dict:
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    access_token = create_access_token({"sub": str(user.id), "role": user.role})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return {
        "user": {
            "id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "avatar_url": user.avatar_url if hasattr(user, "avatar_url") else None,
            "role": user.role,
            "referral_code": user.referral_code,
            "wallet_balance": user.wallet_balance,
            "is_verified": user.is_verified,
        },
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


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


def update_profile(user: User, req: UpdateProfileRequest, db: Session) -> User:
    update_data = req.model_dump(exclude_unset=True)
    if "email" in update_data:
        existing = db.query(User).filter(User.email == req.email, User.id != user.id).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use")
    if "phone" in update_data:
        existing = db.query(User).filter(User.phone == req.phone, User.id != user.id).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone already in use")
    for key, value in update_data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


def change_password(user: User, req: ChangePasswordRequest, db: Session) -> dict:
    if not verify_password(req.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    user.password_hash = hash_password(req.new_password)
    db.commit()
    return {"message": "Password changed successfully"}
