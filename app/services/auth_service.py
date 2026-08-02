from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import verify_password, hash_password
from app.models.user import User
from app.models.enums import UserStatus

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


class AuthError(Exception):
    """Raised for any login failure; message is safe to show the user."""


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email.lower().strip()).first()

    # Constant-ish response regardless of whether the email exists, to avoid
    # leaking which emails are registered.
    if not user:
        raise AuthError("Invalid email or password")

    if user.status == UserStatus.SUSPENDED:
        raise AuthError("This account has been suspended")
    if user.status == UserStatus.INACTIVE:
        raise AuthError("This account is inactive")

    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise AuthError("Account temporarily locked due to failed login attempts. Try again later.")

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
        db.add(user)
        db.commit()
        raise AuthError("Invalid email or password")

    # Success — reset lockout counters
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise AuthError("Current password is incorrect")
    user.password_hash = hash_password(new_password)
    db.add(user)
    db.commit()
