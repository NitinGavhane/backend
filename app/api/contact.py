from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.contact import (
    ContactMessageCreate,
    NewsletterSubscribeRequest,
    SubmitAck,
)
from app.services import contact_service

router = APIRouter(prefix="/api/v1", tags=["Contact"])


@router.post("/contact", response_model=SubmitAck)
def send_contact_message(req: ContactMessageCreate, db: Session = Depends(get_db)):
    """Public: the website's Contact form. Stored for the Admin app to read."""
    return contact_service.create_message(req, db)


@router.post("/newsletter", response_model=SubmitAck)
def subscribe_to_newsletter(req: NewsletterSubscribeRequest, db: Session = Depends(get_db)):
    """Public: the footer's subscribe box."""
    return contact_service.subscribe(req, db)
