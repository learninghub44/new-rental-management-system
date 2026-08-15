"""
Pluggable file storage: local disk for development, S3-compatible object
storage (AWS S3, Supabase Storage, Cloudflare R2, MinIO, ...) for
production. Controlled by settings.STORAGE_BACKEND.

Railway containers are ephemeral — anything written under STORAGE_BACKEND
"local" disappears on every redeploy or restart, so production must run
with STORAGE_BACKEND=s3 and the S3_* settings configured.

Callers should use save_bytes()/delete_object() rather than touching disk
or a storage SDK directly, so the backend can keep changing without
touching call sites (mirrors the intent already noted in upload_service.py).
"""
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("rental_app.storage")


class StorageError(Exception):
    pass


@lru_cache
def _s3_client():
    import boto3

    return boto3.client(
        "s3",
        region_name=settings.S3_REGION or None,
        endpoint_url=settings.S3_ENDPOINT_URL or None,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY or None,
        config=__import__("botocore.config", fromlist=["Config"]).Config(
            s3={"addressing_style": "path" if settings.S3_USE_PATH_STYLE else "auto"}
        ),
    )


def _s3_public_url(key: str) -> str:
    if settings.S3_PUBLIC_URL_BASE:
        return f"{settings.S3_PUBLIC_URL_BASE.rstrip('/')}/{key}"
    if settings.S3_ENDPOINT_URL:
        return f"{settings.S3_ENDPOINT_URL.rstrip('/')}/{settings.S3_BUCKET}/{key}"
    return f"https://{settings.S3_BUCKET}.s3.{settings.S3_REGION}.amazonaws.com/{key}"


def save_bytes(content: bytes, subfolder: str, filename: str, content_type: Optional[str] = None) -> str:
    """Persist `content` under `subfolder/filename` and return a URL to fetch it."""
    key = f"{subfolder}/{filename}"

    if settings.STORAGE_BACKEND == "s3":
        if not settings.S3_BUCKET:
            raise StorageError("STORAGE_BACKEND=s3 but S3_BUCKET is not configured")
        try:
            extra_args = {"ContentType": content_type} if content_type else {}
            _s3_client().put_object(Bucket=settings.S3_BUCKET, Key=key, Body=content, **extra_args)
        except Exception as exc:  # noqa: BLE001 — surface as our own error type
            logger.exception("S3 upload failed for key %s", key)
            raise StorageError(str(exc)) from exc
        return _s3_public_url(key)

    # local
    target_path = Path(settings.UPLOAD_DIR) / subfolder / filename
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(content)
    return f"/static/uploads/{subfolder}/{filename}"


def delete_object(subfolder: str, filename: str) -> None:
    key = f"{subfolder}/{filename}"
    if settings.STORAGE_BACKEND == "s3":
        if not settings.S3_BUCKET:
            return
        try:
            _s3_client().delete_object(Bucket=settings.S3_BUCKET, Key=key)
        except Exception:  # noqa: BLE001 — deletion best-effort, never block the caller
            logger.exception("S3 delete failed for key %s", key)
        return

    target_path = Path(settings.UPLOAD_DIR) / subfolder / filename
    target_path.unlink(missing_ok=True)
