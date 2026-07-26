import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.contact import ContactMessage, NewsletterSubscriber
from app.schemas.contact import ContactMessageCreate, NewsletterSubscribeRequest


def _to_dict(m: ContactMessage) -> dict:
    return {
        "id": str(m.id),
        "full_name": m.full_name,
        "email": m.email,
        "subject": m.subject,
        "message": m.message,
        "is_read": m.is_read,
        "created_at": m.created_at,
    }


def create_message(req: ContactMessageCreate, db: Session) -> dict:
    message = ContactMessage(
        full_name=req.full_name,
        email=req.email,
        subject=(req.subject or "").strip() or None,
        message=req.message,
    )
    db.add(message)
    db.commit()
    return {"message": "Thanks — we've received your message and will get back to you soon."}


def list_messages(db: Session, unread_only: bool = False) -> list[dict]:
    query = db.query(ContactMessage)
    if unread_only:
        query = query.filter(ContactMessage.is_read == False)
    return [_to_dict(m) for m in query.order_by(ContactMessage.created_at.desc()).all()]


def _get(message_id: str, db: Session) -> ContactMessage:
    try:
        mid = uuid.UUID(message_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid message id")
    message = db.query(ContactMessage).filter(ContactMessage.id == mid).first()
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return message


def set_read(message_id: str, is_read: bool, db: Session) -> dict:
    message = _get(message_id, db)
    message.is_read = is_read
    db.commit()
    return _to_dict(message)


def delete_message(message_id: str, db: Session) -> dict:
    message = _get(message_id, db)
    db.delete(message)
    db.commit()
    return {"message": "Message deleted"}


def subscribe(req: NewsletterSubscribeRequest, db: Session) -> dict:
    existing = (
        db.query(NewsletterSubscriber)
        .filter(NewsletterSubscriber.email == req.email)
        .first()
    )
    # Re-subscribing is not an error to the customer — they are on the list
    # either way, and telling them otherwise just looks broken.
    if existing:
        return {"message": "You're already on the list — thanks!"}
    db.add(NewsletterSubscriber(email=req.email))
    db.commit()
    return {"message": "Thanks for subscribing. We'll be in touch with new arrivals."}


def list_subscribers(db: Session) -> list[dict]:
    subscribers = (
        db.query(NewsletterSubscriber)
        .order_by(NewsletterSubscriber.created_at.desc())
        .all()
    )
    return [
        {"id": str(s.id), "email": s.email, "created_at": s.created_at}
        for s in subscribers
    ]
