"""
Application configuration.
All values are loaded from environment variables — no secrets hardcoded.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "Rental Management System"
    ENVIRONMENT: str = "development"  # development | production
    DEBUG: bool = False
    SECRET_KEY: str  # required, no default — must be set in env
    BASE_URL: str = "http://localhost:8000"

    # Database (Supabase Postgres)
    DATABASE_URL: str  # postgresql+psycopg2://user:pass@host:port/dbname

    # JWT
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Rate limiting
    LOGIN_RATE_LIMIT: str = "5/minute"

    # CORS — no wildcard default. Must be set explicitly (see .env.example);
    # combined with allow_credentials=True in main.py, a wildcard here would
    # let any site make authenticated (cookie-carrying) requests.
    ALLOWED_ORIGINS: List[str] = []

    # PayHero
    PAYHERO_API_USERNAME: str = ""
    PAYHERO_API_PASSWORD: str = ""
    PAYHERO_CHANNEL_ID: str = ""
    PAYHERO_CALLBACK_URL: str = ""
    PAYHERO_BASE_URL: str = "https://backend.payhero.co.ke/api/v2"
    # Shared secret appended as a query param to the callback URL we hand PayHero
    # (?secret=...). PayHero's callback payload isn't signed, so this is what
    # proves an inbound webhook actually came from a callback URL we issued,
    # rather than from anyone who can guess/observe a checkout_request_id.
    # Required in production — see app/api/routes/webhooks.py.
    PAYHERO_WEBHOOK_SECRET: str = ""

    # Email (SMTP)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "Rental Management"
    SMTP_USE_TLS: bool = True

    # File storage
    # "local" writes to UPLOAD_DIR on the container's disk — fine for dev,
    # but most PaaS containers (Render, Railway, etc.) are ephemeral, so anything saved this way is
    # lost on every redeploy/restart. Use "s3" in production against any
    # S3-compatible bucket (AWS S3, Supabase Storage, Cloudflare R2, etc).
    STORAGE_BACKEND: str = "local"  # local | s3
    UPLOAD_DIR: str = "app/static/uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    # S3-compatible object storage (used when STORAGE_BACKEND=s3)
    S3_BUCKET: str = ""
    S3_REGION: str = "auto"
    S3_ENDPOINT_URL: str = ""  # set for R2/Supabase/MinIO; leave blank for real AWS S3
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_PUBLIC_URL_BASE: str = ""  # e.g. https://cdn.example.com or the bucket's public endpoint
    S3_USE_PATH_STYLE: bool = True

    # Company info (used on receipts/invoices)
    COMPANY_NAME: str = "Rental Management"
    COMPANY_PHONE: str = ""
    COMPANY_EMAIL: str = ""
    COMPANY_ADDRESS: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
