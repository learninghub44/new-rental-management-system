"""
User-facing file uploads (property images, etc). Validates and hands off to
app/services/storage.py, which is what actually decides local disk vs S3.
"""
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.services.storage import save_bytes, StorageError

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

    try:
        return save_bytes(contents, subfolder, filename, content_type=file.content_type)
    except StorageError as exc:
        raise UploadError(f"Upload failed: {exc}") from exc
