import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Banner(Base):
    __tablename__ = "banners"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    subtitle: Mapped[str] = mapped_column(String(255), nullable=True)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    # How image_url is hosted: "s3" (uploaded to our bucket, file_name holds the
    # key so it can be deleted) or "external" (a pasted third-party URL).
    storage_type: Mapped[str] = mapped_column(String(16), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    link_url: Mapped[str] = mapped_column(String(500), nullable=True)
    link_text: Mapped[str] = mapped_column(String(100), nullable=True)
    section: Mapped[str] = mapped_column(String(50), default="hero")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
