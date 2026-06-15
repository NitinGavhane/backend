from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models.user import User
from app.schemas.banner import BannerCreate, BannerResponse, BannerUpdate
from app.services import banner_service

router = APIRouter(prefix="/api/v1/banners", tags=["Banners"])


@router.get("", response_model=list[BannerResponse])
def list_active_banners(db: Session = Depends(get_db)):
    return banner_service.list_active_banners(db)


@router.get("/all", response_model=list[BannerResponse])
def list_all_banners(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return banner_service.list_all_banners(db)


@router.post("", response_model=BannerResponse, status_code=201)
def create_banner(req: BannerCreate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return banner_service.create_banner(req, db)


@router.get("/{banner_id}", response_model=BannerResponse)
def get_banner(banner_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return banner_service.get_banner(banner_id, db)


@router.put("/{banner_id}", response_model=BannerResponse)
def update_banner(banner_id: str, req: BannerUpdate, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return banner_service.update_banner(banner_id, req, db)


@router.delete("/{banner_id}", status_code=204)
def delete_banner(banner_id: str, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    banner_service.delete_banner(banner_id, db)
