from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.banner import Banner
from app.schemas.banner import BannerCreate, BannerUpdate


def list_active_banners(db: Session) -> list[dict]:
    banners = db.query(Banner).filter(Banner.is_active == True).order_by(Banner.sort_order.asc(), Banner.created_at.desc()).all()
    return [_banner_to_dict(b) for b in banners]


def list_all_banners(db: Session) -> list[dict]:
    banners = db.query(Banner).order_by(Banner.sort_order.asc(), Banner.created_at.desc()).all()
    return [_banner_to_dict(b) for b in banners]


def create_banner(req: BannerCreate, db: Session) -> dict:
    banner = Banner(**req.model_dump())
    db.add(banner)
    db.commit()
    db.refresh(banner)
    return _banner_to_dict(banner)


def get_banner(banner_id: str, db: Session) -> dict:
    banner = db.query(Banner).filter(Banner.id == banner_id).first()
    if not banner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")
    return _banner_to_dict(banner)


def update_banner(banner_id: str, req: BannerUpdate, db: Session) -> dict:
    banner = db.query(Banner).filter(Banner.id == banner_id).first()
    if not banner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")
    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(banner, key, value)
    db.commit()
    db.refresh(banner)
    return _banner_to_dict(banner)


def delete_banner(banner_id: str, db: Session) -> None:
    banner = db.query(Banner).filter(Banner.id == banner_id).first()
    if not banner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")
    db.delete(banner)
    db.commit()


def _banner_to_dict(banner: Banner) -> dict:
    return {
        "id": str(banner.id),
        "image_url": banner.image_url,
        "title": banner.title,
        "subtitle": banner.subtitle,
        "link_url": banner.link_url,
        "link_text": banner.link_text,
        "sort_order": banner.sort_order,
        "is_active": banner.is_active,
        "created_at": banner.created_at,
        "updated_at": banner.updated_at,
    }
