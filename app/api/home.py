from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import home_service

router = APIRouter(prefix="/api/v1/home", tags=["Home"])


@router.get("")
def get_home(db: Session = Depends(get_db)):
    return home_service.get_home_content(db)


@router.get("/{section}")
def get_home_section(section: str, db: Session = Depends(get_db)):
    return home_service.get_home_section(section, db)
