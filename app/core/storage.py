import os
import uuid
from pathlib import Path

from fastapi import UploadFile

UPLOAD_DIR = Path("static/uploads/categories")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


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
