from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.product import ProductResponse
from app.services import product_service

router = APIRouter(prefix="/api/v1/products", tags=["Products"])


@router.get("")
def list_products(
    category: str | None = Query(None),
    search: str | None = Query(None),
    sort: str | None = Query(None),
    featured: bool | None = Query(None),
    gender: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return product_service.list_products(db, category, search, sort, featured, gender)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: str, db: Session = Depends(get_db)):
    return product_service.get_product(product_id, db)
