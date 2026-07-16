from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core import storage
from app.core.deps import get_current_admin
from app.models.user import User

router = APIRouter(prefix="/api/v1", tags=["Uploads"])


@router.post("/upload")
async def upload_image(file: UploadFile = File(...), admin: User = Depends(get_current_admin)):
    """Admin-only image upload for banners (and other admin media).

    Returns {"url": "<public image url>"} which the Admin app stores in the
    banner's image_url. Validation happens in storage.upload_image_to_s3.
    """
    contents = await file.read()
    try:
        url = storage.upload_image_to_s3(contents, file.filename, file.content_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"url": url}
