from typing import Optional
from sqlalchemy.orm import Session
from app.models.product import Product


def get_products(
    db: Session,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sizes: Optional[str] = None,
    colors: Optional[str] = None,
    sort_by: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    query = db.query(Product)

    if category:
        query = query.filter(Product.category_id == category)
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if sizes:
        size_list = [s.strip() for s in sizes.split(",")]
        from sqlalchemy import cast, String
        query = query.filter(
            Product.sizes.any(size_list[0])
        )
    if colors:
        color_list = [c.strip() for c in colors.split(",")]
        query = query.filter(Product.colors.any(color_list[0]))

    if sort_by == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort_by == "price_desc":
        query = query.order_by(Product.price.desc())
    elif sort_by == "rating":
        query = query.order_by(Product.rating.desc())
    elif sort_by == "newest":
        query = query.order_by(Product.is_new.desc())
    elif sort_by == "popular":
        query = query.order_by(Product.review_count.desc())
    else:
        query = query.order_by(Product.title.asc())

    total = query.count()
    products = query.offset((page - 1) * limit).limit(limit).all()

    return {
        "products": [p.to_dict() for p in products],
        "total": total,
        "page": page,
        "limit": limit,
        "totalPages": (total + limit - 1) // limit,
    }


def get_product(db: Session, product_id: str) -> Product:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


def get_featured_products(db: Session) -> list:
    return [p.to_dict() for p in db.query(Product).filter(Product.is_featured == True).all()]


def get_new_arrivals(db: Session) -> list:
    return [p.to_dict() for p in db.query(Product).filter(Product.is_new == True).all()]


def get_products_by_category(db: Session, category_id: str) -> list:
    return [p.to_dict() for p in db.query(Product).filter(Product.category_id == category_id).all()]


def search_products(db: Session, q: str, page: int = 1, limit: int = 20) -> dict:
    query = db.query(Product).filter(
        Product.title.ilike(f"%{q}%")
        | Product.brand.ilike(f"%{q}%")
        | Product.category.ilike(f"%{q}%")
    )
    total = query.count()
    products = query.offset((page - 1) * limit).limit(limit).all()
    return {
        "products": [p.to_dict() for p in products],
        "total": total,
        "page": page,
        "limit": limit,
        "totalPages": (total + limit - 1) // limit,
    }
