"""
Local disk-based file storage. Files are saved under app/static/uploads and
served directly by StaticFiles — swap for S3/Cloudflare R2 by replacing
save_upload() without touching callers.
"""
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


class UploadError(Exception):
    pass


async def save_upload(file: UploadFile, subfolder: str) -> str:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise UploadError("Only JPEG, PNG, or WEBP images are allowed")

    contents = await file.read()
    if len(contents) > MAX_SIZE_BYTES:
        raise UploadError(f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB limit")

    ext = Path(file.filename or "").suffix.lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"

    target_dir = Path(settings.UPLOAD_DIR) / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    target_path.write_bytes(contents)

    return f"/static/uploads/{subfolder}/{filename}"
