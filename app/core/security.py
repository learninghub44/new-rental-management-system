"""
Password hashing and JWT token creation/verification.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


class TokenPayload(BaseModel):
    sub: str  # user id
    role: str
    exp: datetime
    type: str  # "access" | "refresh"


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "role": role, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: uuid.UUID, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "role": role, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


def create_password_reset_token() -> str:
    """Raw token given to the user (emailed). Only its hash is stored server-side."""
    import secrets

    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    """One-way hash for storing reset tokens — reuses bcrypt for consistency."""
    return pwd_context.hash(raw_token)


def verify_token_hash(raw_token: str, token_hash: str) -> bool:
    return pwd_context.verify(raw_token, token_hash)
