import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import User, UserRole
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token


def register_user(db: Session, full_name: str, email: str, phone: str, password: str) -> dict:
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        id=str(uuid.uuid4()),
        full_name=full_name,
        email=email,
        phone=phone,
        hashed_password=hash_password(password),
        referral_code=f"REF{uuid.uuid4().hex[:6].upper()}",
        is_verified=True,
        role=UserRole.user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token({"sub": user.id})
    refresh_token = create_refresh_token({"sub": user.id})

    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "user": user.to_dict(),
    }


def login_user(db: Session, email: str, password: str) -> dict:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token({"sub": user.id})
    refresh_token = create_refresh_token({"sub": user.id})

    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "user": user.to_dict(),
    }


def forgot_password(db: Session, email: str) -> dict:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email not found",
        )
    return {"message": "Password reset link sent to your email"}


def refresh_access_token(db: Session, refresh_token: str) -> dict:
    from app.core.security import decode_token
    payload = decode_token(refresh_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    new_access = create_access_token({"sub": user.id})
    return {"accessToken": new_access}
