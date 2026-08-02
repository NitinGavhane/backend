from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core import storage
from app.core.deps import get_current_admin, get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1", tags=["Uploads"])


@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    folder: str = Form(storage.DEFAULT_PREFIX),
    admin: User = Depends(get_current_admin),
):
    """Admin-only image upload for banners, products and categories.

    `folder` selects the S3 key prefix and must be one of storage.IMAGE_PREFIXES.
    Returns the public URL plus the metadata the Admin app echoes back when it
    saves the entity. Validation happens in storage.upload_image_to_s3.
    """
    contents = await file.read()
    try:
        if folder not in storage.IMAGE_PREFIXES:
            raise ValueError(f"Unsupported upload folder. Allowed folders: {', '.join(storage.IMAGE_PREFIXES)}")
        stored = storage.upload_image_to_s3(contents, file.filename, file.content_type, folder)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {
        "url": stored.url,
        "file_name": stored.key,
        "storage_type": storage.STORAGE_S3,
    }


@router.post("/upload/return-evidence")
async def upload_return_evidence(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Signed-in customer uploads return/replace evidence (photos of the item).

    Stored under the dedicated 'returns' prefix; distinct from the admin upload
    so a customer can never write into banners/products/categories.
    """
    contents = await file.read()
    try:
        stored = storage.upload_image_to_s3(contents, file.filename, file.content_type, "returns")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {
        "url": stored.url,
        "file_name": stored.key,
        "storage_type": storage.STORAGE_S3,
    }
