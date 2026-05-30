from sqlalchemy.orm import Session
from app.models.category import Category


def get_categories(db: Session) -> list:
    return [c.to_dict() for c in db.query(Category).all()]
