import io
import logging
import uuid
from datetime import datetime, timezone
from typing import NamedTuple
from urllib.parse import unquote, urlparse

from app.core.config import settings

logger = logging.getLogger(__name__)

# Image upload rules (kept in sync with the specs shown in the Admin app).
IMAGE_MAX_SIZE = 5 * 1024 * 1024  # 5 MB
IMAGE_MIN_WIDTH = 600
IMAGE_MIN_HEIGHT = 400
# Pillow format name -> (canonical extension, content type)
_IMAGE_FORMATS = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}

# S3 key prefixes an admin may upload into via /upload. Anything else is
# rejected so a client cannot write to arbitrary locations in the bucket.
IMAGE_PREFIXES = ("banners", "products", "categories")
DEFAULT_PREFIX = "banners"
# Every prefix upload_image_to_s3 may store under. "returns" is added here so
# the customer-facing /upload/return-evidence route can use the same validator,
# but it is deliberately NOT in IMAGE_PREFIXES — the admin upload route checks
# that tuple, so an admin panel can never touch customer evidence.
ALLOWED_PREFIXES = IMAGE_PREFIXES + ("returns",)

# Values stored in the *.storage_type columns.
STORAGE_S3 = "s3"
STORAGE_EXTERNAL = "external"


class StoredImage(NamedTuple):
    """An image persisted to S3: its public URL and the bucket key."""

    url: str
    key: str


def _public_base() -> str:
    """Base URL images are served from (a CDN if configured, else raw S3)."""
    if settings.S3_PUBLIC_BASE_URL:
        return settings.S3_PUBLIC_BASE_URL.rstrip("/")
    return f"https://{settings.S3_UPLOAD_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com"


def s3_url_bases() -> list[str]:
    """Every base URL that identifies an object in our own bucket.

    Both forms are recognised because rows written before S3_PUBLIC_BASE_URL was
    configured hold direct S3 URLs, while newer rows hold CDN URLs.
    """
    bases = []
    if settings.S3_UPLOAD_BUCKET:
        bases.append(f"https://{settings.S3_UPLOAD_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com")
        bases.append(f"https://{settings.S3_UPLOAD_BUCKET}.s3.amazonaws.com")
    if settings.S3_PUBLIC_BASE_URL:
        bases.append(settings.S3_PUBLIC_BASE_URL.rstrip("/"))
    # Longest first so a CDN base that shares a host with another entry wins.
    return sorted(set(bases), key=len, reverse=True)


def s3_key_for_url(image_url: str | None) -> str | None:
    """Return the bucket key if image_url points at our own bucket, else None.

    The key is derived from the URL rather than trusted from the client, so a
    single rule classifies newly-uploaded images, legacy rows, and images an
    admin pasted in as external links.
    """
    if not image_url:
        return None
    url = image_url.strip()
    for base in s3_url_bases():
        if url.startswith(base + "/"):
            key = unquote(urlparse(url[len(base) + 1 :]).path)
            return key or None
    return None


def image_metadata(image_url: str | None) -> dict:
    """Derive the stored image metadata columns for an image URL.

    Returns storage_type ('s3' or 'external'), file_name (the S3 key, or None
    for external URLs) and uploaded_at.
    """
    if not image_url or not image_url.strip():
        return {"storage_type": None, "file_name": None, "uploaded_at": None}
    key = s3_key_for_url(image_url)
    return {
        "storage_type": STORAGE_S3 if key else STORAGE_EXTERNAL,
        "file_name": key,
        "uploaded_at": datetime.now(timezone.utc),
    }


def upload_image_to_s3(
    contents: bytes,
    filename: str | None,
    content_type: str | None,
    prefix: str = DEFAULT_PREFIX,
) -> StoredImage:
    """Validate an uploaded image and store it in S3.

    Validation (also enforced client-side in the Admin app): allowed formats
    JPG/PNG/WebP, max 5 MB, minimum 600x400. Raises ValueError on any rule
    violation so the route can surface a 400 with a helpful message.
    """
    if not settings.S3_UPLOAD_BUCKET:
        raise ValueError("Image upload is not configured on the server (missing S3 bucket)")

    if prefix not in ALLOWED_PREFIXES:
        raise ValueError(f"Unsupported upload folder. Allowed folders: {', '.join(IMAGE_PREFIXES)}")

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
    key = f"{prefix}/{uuid.uuid4().hex}{ext}"

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

    return StoredImage(url=f"{_public_base()}/{key}", key=key)


def delete_image_from_s3(image_url: str | None) -> bool:
    """Best-effort delete of the S3 object behind image_url.

    External URLs are left alone (nothing of ours to delete). S3 failures are
    logged and swallowed: an unreachable bucket must never block the admin from
    deleting the database row, at the cost of a possible orphaned object.
    Returns True only when an object was actually deleted.
    """
    key = s3_key_for_url(image_url)
    if not key or not settings.S3_UPLOAD_BUCKET:
        return False
    try:
        import boto3

        s3 = boto3.client("s3", region_name=settings.AWS_REGION)
        s3.delete_object(Bucket=settings.S3_UPLOAD_BUCKET, Key=key)
        return True
    except Exception:
        logger.exception("Failed to delete S3 object %s; leaving it orphaned", key)
        return False


def delete_images_from_s3(image_urls) -> int:
    """Best-effort delete of several images. Returns the number removed."""
    return sum(1 for url in image_urls if delete_image_from_s3(url))
