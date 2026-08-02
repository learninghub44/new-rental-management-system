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

    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]

    # PayHero
    PAYHERO_API_USERNAME: str = ""
    PAYHERO_API_PASSWORD: str = ""
    PAYHERO_CHANNEL_ID: str = ""
    PAYHERO_CALLBACK_URL: str = ""
    PAYHERO_BASE_URL: str = "https://backend.payhero.co.ke/api/v2"

    # Email (SMTP)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "Rental Management"
    SMTP_USE_TLS: bool = True

    # File storage
    UPLOAD_DIR: str = "app/static/uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    # Company info (used on receipts/invoices)
    COMPANY_NAME: str = "Rental Management"
    COMPANY_PHONE: str = ""
    COMPANY_EMAIL: str = ""
    COMPANY_ADDRESS: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
