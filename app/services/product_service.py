import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.category import Category
from app.models.product import Product, ProductImage, ProductVariant
from app.schemas.product import ProductCreate, ProductUpdate


def list_products(db: Session, category: str | None = None, search: str | None = None, sort: str | None = None, featured: bool | None = None, gender: str | None = None):
    query = db.query(Product).options(joinedload(Product.category), joinedload(Product.images), joinedload(Product.variants)).filter(Product.is_active == True)
    if category:
        query = query.filter(Product.category_id == _parse_uuid(category, "category_id"))
    if search:
        query = query.filter(Product.title.ilike(f"%{search}%"))
    if featured is not None:
        query = query.filter(Product.featured == featured)
    if gender:
        query = query.filter(Product.gender == gender)
    if sort == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price.desc())
    elif sort == "newest":
        query = query.order_by(Product.created_at.desc())
    else:
        query = query.order_by(Product.created_at.desc())
    products = query.all()
    result = []
    for p in products:
        primary_image = next((img.image_url for img in p.images if img.is_primary), (p.images[0].image_url if p.images else None))
        result.append({
            "id": str(p.id),
            "title": p.title,
            "sku": p.sku,
            "price": p.price,
            "discount_price": p.discount_price,
            "stock": p.stock,
            "featured": p.featured,
            "is_active": p.is_active,
            "gender": p.gender,
            "category_id": str(p.category_id),
            "category_name": p.category.name if p.category else None,
            "primary_image": primary_image,
        })
    return result


def get_product(product_id: str, db: Session):
    pid = _parse_uuid(product_id, "product_id")
    product = db.query(Product).options(joinedload(Product.category), joinedload(Product.images), joinedload(Product.variants)).filter(Product.id == pid).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return {
        "id": str(product.id),
        "category_id": str(product.category_id),
        "title": product.title,
        "description": product.description,
        "brand": product.brand,
        "sku": product.sku,
        "price": product.price,
        "discount_price": product.discount_price,
        "gst_percentage": product.gst_percentage,
        "stock": product.stock,
        "featured": product.featured,
        "gender": product.gender,
        "is_active": product.is_active,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
        "variants": [{"id": str(v.id), "size": v.size, "color": v.color, "stock": v.stock, "price": v.price} for v in product.variants],
        "images": [{"id": str(img.id), "image_url": img.image_url, "is_primary": img.is_primary} for img in product.images],
    }


def _parse_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid {field}: must be a valid UUID")


def create_product(req: ProductCreate, db: Session):
    category_id = _parse_uuid(req.category_id, "category_id")
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    product = Product(
        category_id=category_id,
        title=req.title,
        description=req.description,
        brand=req.brand,
        sku=req.sku,
        price=req.price,
        discount_price=req.discount_price,
        gst_percentage=req.gst_percentage,
        stock=req.stock,
        featured=req.featured,
        gender=req.gender if req.gender else category.gender,
    )
    db.add(product)
    db.flush()
    for v in req.variants:
        variant = ProductVariant(product_id=product.id, size=v.size, color=v.color, stock=v.stock, price=v.price)
        db.add(variant)
    for img in req.images:
        image = ProductImage(product_id=product.id, image_url=img.image_url, is_primary=img.is_primary)
        db.add(image)
    db.commit()
    db.refresh(product)
    return get_product(str(product.id), db)


def update_product(product_id: str, req: ProductUpdate, db: Session):
    pid = _parse_uuid(product_id, "product_id")
    product = db.query(Product).filter(Product.id == pid).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    update_data = req.model_dump(exclude_unset=True)
    if "category_id" in update_data:
        update_data["category_id"] = _parse_uuid(update_data["category_id"], "category_id")
        new_cat = db.query(Category).filter(Category.id == update_data["category_id"]).first()
        if new_cat:
            update_data.setdefault("gender", new_cat.gender)
    images_data = update_data.pop("images", None)
    for key, value in update_data.items():
        setattr(product, key, value)
    if images_data is not None:
        for img in product.images:
            db.delete(img)
        for img_data in images_data:
            image = ProductImage(product_id=product.id, image_url=img_data["image_url"], is_primary=img_data.get("is_primary", False))
            db.add(image)
    db.commit()
    db.refresh(product)
    return get_product(str(product.id), db)


def delete_product(product_id: str, db: Session):
    pid = _parse_uuid(product_id, "product_id")
    product = db.query(Product).filter(Product.id == pid).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    db.delete(product)
    db.commit()
    return {"message": "Product deleted successfully"}
