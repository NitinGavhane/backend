from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UpdateProfileRequest
from app.services import user_service

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/profile")
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return user_service.get_profile(db, current_user.id)


@router.put("/profile")
def update_profile(
    req: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return user_service.update_profile(
        db, current_user.id, req.fullName, req.phone, req.avatarUrl
    )
