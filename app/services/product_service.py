import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core import gst, storage
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
        sizes = sorted(set(v.size for v in p.variants if v.size))
        colors = sorted(set(v.color for v in p.variants if v.color))
        discount_pct = round(((p.price - p.discount_price) / p.price) * 100, 1) if p.discount_price is not None and p.discount_price < p.price else 0.0
        is_new_flag = p.created_at and (datetime.now(timezone.utc) - p.created_at).days < 30
        result.append({
            "id": str(p.id),
            "title": p.title,
            "sku": p.sku,
            "brand": p.brand,
            "description": p.description,
            "price": p.discount_price if p.discount_price is not None else p.price,
            "original_price": p.price,
            "discount_percentage": discount_pct,
            "rating": 0.0,
            "review_count": 0,
            "stock": p.stock,
            "image_url": primary_image,
            "category_id": str(p.category_id),
            "category_name": p.category.name if p.category else None,
            "sizes": sizes,
            "colors": colors,
            "gradient_colors": [],
            "gender": p.gender,
            "is_featured": p.featured,
            "is_new": is_new_flag,
            "is_popular": False,
            "is_replaceable": p.is_replaceable,
            "is_returnable": p.is_returnable,
        })
    return result


def _gst_fields() -> dict:
    """Fixed GST rates shown to buyers. Nothing is configured per product; the
    seller is in West Bengal, so browse-time display uses the intra-state split
    (CGST + SGST). The inter-state IGST rate is exposed for reference/invoicing.
    """
    return {
        "cgst_percentage": gst.CGST_PERCENTAGE,
        "sgst_percentage": gst.SGST_PERCENTAGE,
        "igst_percentage": gst.IGST_PERCENTAGE,
    }


def _variant_to_dict(v):
    return {
        "id": str(v.id),
        "size": v.size,
        "color": v.color,
        "stock": v.stock,
        "price": v.price,
    }


def _image_to_dict(img):
    return {
        "id": str(img.id),
        "image_url": img.image_url,
        "is_primary": img.is_primary,
        "storage_type": img.storage_type,
        "file_name": img.file_name,
        "uploaded_at": img.uploaded_at,
    }


def get_product(product_id: str, db: Session):
    pid = _parse_uuid(product_id, "product_id")
    product = db.query(Product).options(joinedload(Product.category), joinedload(Product.images), joinedload(Product.variants)).filter(Product.id == pid).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    primary_image = next((img.image_url for img in product.images if img.is_primary), (product.images[0].image_url if product.images else None))
    sizes = sorted(set(v.size for v in product.variants if v.size))
    colors = sorted(set(v.color for v in product.variants if v.color))
    discount_pct = round(((product.price - product.discount_price) / product.price) * 100, 1) if product.discount_price and product.discount_price < product.price else 0.0
    is_new_flag = product.created_at and (datetime.now(timezone.utc) - product.created_at).days < 30
    return {
        "id": str(product.id),
        "title": product.title,
        "brand": product.brand,
        "description": product.description,
        "sku": product.sku,
        "price": product.discount_price or product.price,
        "original_price": product.price,
        "discount_percentage": discount_pct,
        "rating": 0.0,
        "review_count": 0,
        "stock": product.stock,
        "image_url": primary_image,
        "category_id": str(product.category_id),
        "category_name": product.category.name if product.category else None,
        "sizes": sizes,
        "colors": colors,
        "gender": product.gender,
        **_gst_fields(),
        "is_active": product.is_active,
        "is_featured": product.featured,
        "is_new": is_new_flag,
        "is_popular": False,
        "is_replaceable": product.is_replaceable,
        "is_returnable": product.is_returnable,
        "gradient_colors": [],
        "variants": [_variant_to_dict(v) for v in product.variants],
        "images": [_image_to_dict(img) for img in product.images],
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
    }


def get_admin_product(product_id: str, db: Session):
    pid = _parse_uuid(product_id, "product_id")
    product = db.query(Product).options(joinedload(Product.category), joinedload(Product.images), joinedload(Product.variants)).filter(Product.id == pid).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    primary_image = next((img.image_url for img in product.images if img.is_primary), (product.images[0].image_url if product.images else None))
    return {
        "id": str(product.id),
        "title": product.title,
        "sku": product.sku,
        "price": product.price,
        "discount_price": product.discount_price,
        "stock": product.stock,
        "featured": product.featured,
        "is_active": product.is_active,
        "is_replaceable": product.is_replaceable,
        "is_returnable": product.is_returnable,
        "category_id": str(product.category_id),
        "category_name": product.category.name if product.category else None,
        "primary_image": primary_image,
        "description": product.description,
        "brand": product.brand,
        "gender": product.gender,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
        "variants": [_variant_to_dict(v) for v in product.variants],
        "images": [_image_to_dict(img) for img in product.images],
    }


def list_admin_products(db: Session, gender: str | None = None):
    query = db.query(Product).options(joinedload(Product.category), joinedload(Product.images), joinedload(Product.variants))
    if gender:
        query = query.filter(Product.gender == gender)
    products = query.order_by(Product.created_at.desc()).all()
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
            "is_replaceable": p.is_replaceable,
            "is_returnable": p.is_returnable,
            "category_id": str(p.category_id),
            "category_name": p.category.name if p.category else None,
            "primary_image": primary_image,
            "description": p.description,
            "brand": p.brand,
            "gender": p.gender,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            "variants": [_variant_to_dict(v) for v in p.variants],
            "images": [_image_to_dict(img) for img in p.images],
        })
    return result


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
        stock=req.stock,
        featured=req.featured,
        is_replaceable=req.is_replaceable,
        is_returnable=req.is_returnable,
        gender=req.gender if req.gender else category.gender,
    )
    db.add(product)
    db.flush()
    for v in req.variants:
        variant = ProductVariant(product_id=product.id, size=v.size, color=v.color, stock=v.stock, price=v.price)
        db.add(variant)
    for img in req.images:
        image = ProductImage(
            product_id=product.id,
            image_url=img.image_url,
            is_primary=img.is_primary,
            **storage.image_metadata(img.image_url),
        )
        db.add(image)
    db.commit()
    db.refresh(product)
    return get_admin_product(str(product.id), db)


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
    removed_images = []
    if images_data is not None:
        # The image list is replaced wholesale, so only the images that are gone
        # from the new list get their S3 objects dropped — a URL the admin kept
        # is re-inserted below and must keep its object.
        kept_urls = {img_data["image_url"] for img_data in images_data}
        removed_images = [img.image_url for img in product.images if img.image_url not in kept_urls]
        # Carry the original upload time across a rewrite of an unchanged image.
        uploaded_at_by_url = {img.image_url: img.uploaded_at for img in product.images}
        for img in product.images:
            db.delete(img)
        db.flush()
        for img_data in images_data:
            url = img_data["image_url"]
            metadata = storage.image_metadata(url)
            if uploaded_at_by_url.get(url):
                metadata["uploaded_at"] = uploaded_at_by_url[url]
            image = ProductImage(
                product_id=product.id,
                image_url=url,
                is_primary=img_data.get("is_primary", False),
                **metadata,
            )
            db.add(image)
    db.commit()
    db.refresh(product)
    storage.delete_images_from_s3(removed_images)
    return get_admin_product(str(product.id), db)


def delete_product(product_id: str, db: Session):
    pid = _parse_uuid(product_id, "product_id")
    product = db.query(Product).filter(Product.id == pid).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    image_urls = [img.image_url for img in product.images]
    db.delete(product)
    db.commit()
    storage.delete_images_from_s3(image_urls)
    return {"message": "Product deleted successfully"}
