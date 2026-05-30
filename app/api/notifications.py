from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services import notification_service

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("")
def get_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notifications = notification_service.get_notifications(db, current_user.id)
    return {"notifications": notifications}


@router.put("/{notification_id}/read")
def mark_as_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return notification_service.mark_as_read(db, current_user.id, notification_id)


@router.put("/read-all")
def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return notification_service.mark_all_as_read(db, current_user.id)
