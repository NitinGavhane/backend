from sqlalchemy.orm import Session

from app.core import storage
from app.models.banner import Banner
from app.models.product import Product


def _primary_image(product: Product) -> str | None:
    """The image the seller marked primary, falling back to the first one.

    Matches product_service so the home feed, listings and the product page all
    show the same photo.
    """
    return storage.serve_image_url(
        next(
            (img.image_url for img in product.images if img.is_primary),
            product.images[0].image_url if product.images else None,
        )
    )


def get_home_content(db: Session):
    banners = db.query(Banner).filter(Banner.is_active == True).order_by(Banner.sort_order.asc()).all()
    featured_products = db.query(Product).filter(Product.is_active == True, Product.featured == True).order_by(Product.created_at.desc()).limit(10).all()
    new_products = db.query(Product).filter(Product.is_active == True).order_by(Product.created_at.desc()).limit(10).all()
    return {
        "banners": [
            {
                "id": str(b.id),
                "title": b.title,
                "subtitle": b.subtitle,
                "image_url": b.image_url,
                "link_url": b.link_url,
                "link_text": b.link_text,
                "section": b.section,
                "sort_order": b.sort_order,
            }
            for b in banners
        ],
        "featured_products": [
            {
                "id": str(p.id),
                "title": p.title,
                "price": p.discount_price or p.price,
                "original_price": p.price,
                "image_url": _primary_image(p),
            }
            for p in featured_products
        ],
        "new_arrivals": [
            {
                "id": str(p.id),
                "title": p.title,
                "price": p.discount_price or p.price,
                "original_price": p.price,
                "image_url": _primary_image(p),
            }
            for p in new_products
        ],
    }


def get_home_section(section: str, db: Session):
    banners = db.query(Banner).filter(Banner.is_active == True, Banner.section == section).order_by(Banner.sort_order.asc()).all()
    return [
        {
            "id": str(b.id),
            "title": b.title,
            "subtitle": b.subtitle,
            "image_url": b.image_url,
            "link_url": b.link_url,
            "link_text": b.link_text,
            "section": b.section,
            "sort_order": b.sort_order,
        }
        for b in banners
    ]
