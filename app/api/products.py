from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.services import product_service

router = APIRouter(prefix="/api/products", tags=["Products"])


@router.get("")
def list_products(
    category: Optional[str] = Query(None),
    minPrice: Optional[float] = Query(None),
    maxPrice: Optional[float] = Query(None),
    sizes: Optional[str] = Query(None),
    colors: Optional[str] = Query(None),
    sortBy: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return product_service.get_products(
        db, category, minPrice, maxPrice, sizes, colors, sortBy, page, limit
    )


@router.get("/search")
def search_products(
    q: str = Query(""),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return product_service.search_products(db, q, page, limit)


@router.get("/featured")
def featured_products(db: Session = Depends(get_db)):
    return {"products": product_service.get_featured_products(db)}


@router.get("/new-arrivals")
def new_arrivals(db: Session = Depends(get_db)):
    return {"products": product_service.get_new_arrivals(db)}


@router.get("/category/{category_id}")
def products_by_category(category_id: str, db: Session = Depends(get_db)):
    return {"products": product_service.get_products_by_category(db, category_id)}


@router.get("/{product_id}")
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = product_service.get_product(db, product_id)
    return product.to_dict()
