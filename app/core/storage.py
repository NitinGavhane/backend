import io
import os
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings

UPLOAD_DIR = Path("static/uploads/categories")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

# Banner image upload rules (kept in sync with the specs shown in the Admin app).
IMAGE_MAX_SIZE = 5 * 1024 * 1024  # 5 MB
IMAGE_MIN_WIDTH = 600
IMAGE_MIN_HEIGHT = 400
# Pillow format name -> (canonical extension, content type)
_IMAGE_FORMATS = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}


def upload_image_to_s3(contents: bytes, filename: str | None, content_type: str | None) -> str:
    """Validate an uploaded image and store it in S3, returning its public URL.

    Validation (also enforced client-side in the Admin app): allowed formats
    JPG/PNG/WebP, max 5 MB, minimum 600x400. Raises ValueError on any rule
    violation so the route can surface a 400 with a helpful message.
    """
    if not settings.S3_UPLOAD_BUCKET:
        raise ValueError("Image upload is not configured on the server (missing S3 bucket)")

    if len(contents) > IMAGE_MAX_SIZE:
        raise ValueError("File too large. Maximum size is 5 MB")
    if not contents:
        raise ValueError("Empty file")

    # Pillow is the source of truth for the real format/dimensions — never trust
    # the client-supplied filename or content-type alone.
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(contents)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(contents)) as probe:
            fmt = (probe.format or "").upper()
            width, height = probe.size
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValueError("Invalid or corrupted image file")

    if fmt not in _IMAGE_FORMATS:
        raise ValueError("Unsupported image format. Allowed formats: JPG, PNG, WebP")
    if width < IMAGE_MIN_WIDTH or height < IMAGE_MIN_HEIGHT:
        raise ValueError(
            f"Image too small ({width}x{height}). Minimum is {IMAGE_MIN_WIDTH}x{IMAGE_MIN_HEIGHT}px"
        )

    ext, ct = _IMAGE_FORMATS[fmt]
    key = f"banners/{uuid.uuid4().hex}{ext}"

    # boto3 picks up credentials from the EC2 instance role at runtime.
    import boto3

    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    s3.put_object(
        Bucket=settings.S3_UPLOAD_BUCKET,
        Key=key,
        Body=contents,
        ContentType=ct,
        CacheControl="public, max-age=31536000",
    )

    if settings.S3_PUBLIC_BASE_URL:
        base = settings.S3_PUBLIC_BASE_URL.rstrip("/")
    else:
        base = f"https://{settings.S3_UPLOAD_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com"
    return f"{base}/{key}"


def ensure_upload_dir():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def save_category_image(file: UploadFile) -> str:
    ensure_upload_dir()

    ext = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}")

    contents = file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise ValueError("File too large. Maximum size is 5 MB")

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = UPLOAD_DIR / filename

    with open(filepath, "wb") as f:
        f.write(contents)

    return f"/static/uploads/categories/{filename}"


def delete_category_image(image_url: str | None):
    if not image_url:
        return
    relative_path = image_url.lstrip("/")
    filepath = Path(relative_path)
    if filepath.exists():
        filepath.unlink()
