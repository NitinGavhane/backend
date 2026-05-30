from sqlalchemy import Column, String, ForeignKey, Table
from sqlalchemy.orm import relationship
from app.core.database import Base


wishlist_table = Table(
    "wishlist",
    Base.metadata,
    Column("user_id", String, ForeignKey("users.id"), primary_key=True),
    Column("product_id", String, ForeignKey("products.id"), primary_key=True),
)
