from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services import category_service

router = APIRouter(prefix="/api/categories", tags=["Categories"])


@router.get("")
def list_categories(db: Session = Depends(get_db)):
    return {"categories": category_service.get_categories(db)}
