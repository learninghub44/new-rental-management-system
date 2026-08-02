"""
Auth dependencies. Session token is stored in an HttpOnly cookie
(this is a server-rendered HTMX app, not a pure JSON SPA), with a
bearer-header fallback so the same endpoints can serve a future API client.
"""
import uuid
from typing import Optional

from fastapi import Depends, Request, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.models.enums import UserRole, UserStatus

COOKIE_NAME = "access_token"


def _extract_token(request: Request) -> Optional[str]:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1]
    return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    return user


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None


class RequireRole:
    """Dependency factory: RequireRole(UserRole.ADMIN, UserRole.ACCOUNTANT)"""

    def __init__(self, *allowed_roles: UserRole):
        self.allowed_roles = set(allowed_roles)

    def __call__(self, user: User = Depends(get_current_user)) -> User:
        if user.role not in self.allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user


require_admin = RequireRole(UserRole.ADMIN)
require_admin_or_accountant = RequireRole(UserRole.ADMIN, UserRole.ACCOUNTANT)
require_staff = RequireRole(UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.CARETAKER)
require_tenant = RequireRole(UserRole.TENANT)
