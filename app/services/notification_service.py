import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.notification import Notification


def get_notifications(db: Session, user_id: str) -> list:
    notifications = db.query(Notification).filter(
        Notification.user_id == user_id
    ).order_by(Notification.created_at.desc()).all()
    return [n.to_dict() for n in notifications]


def mark_as_read(db: Session, user_id: str, notification_id: str) -> dict:
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user_id,
    ).first()
    if not notification:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notification.is_read = True
    db.commit()
    return notification.to_dict()


def mark_all_as_read(db: Session, user_id: str) -> dict:
    db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"marked": True}


def create_notification(db: Session, user_id: str, title: str, message: str, notif_type: str = "info") -> dict:
    notification = Notification(
        id=str(uuid.uuid4()),
        user_id=user_id,
        title=title,
        message=message,
        type=notif_type,
        is_read=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification.to_dict()
