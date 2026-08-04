import uuid
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.phone import default_password_from_phone
from app.models.user import User
from app.models.enums import UserRole, UserStatus
from app.schemas.user import UserCreate, UserUpdate


class UserServiceError(Exception):
    """Raised for user-facing validation errors (duplicate email/phone, etc)."""


def list_users(
    db: Session,
    search: Optional[str] = None,
    role: Optional[UserRole] = None,
    status_filter: Optional[UserStatus] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[User], int]:
    query = db.query(User)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like), User.phone.ilike(like)))
    if role:
        query = query.filter(User.role == role)
    if status_filter:
        query = query.filter(User.status == status_filter)

    total = query.count()
    items = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def create_user(db: Session, data: UserCreate) -> tuple[User, str]:
    """
    Creates a user with the initial password set to the last 6 digits of
    their phone number (business rule: no self sign-up, admin provisions
    every account and hands the tenant/staff member their starting login).
    Returns (user, plaintext_default_password) so the caller can display/
    communicate it once — it is never stored or logged in plaintext.
    """
    existing = db.query(User).filter(or_(User.email == data.email.lower(), User.phone == data.phone)).first()
    if existing:
        field = "email" if existing.email == data.email.lower() else "phone"
        raise UserServiceError(f"A user with this {field} already exists")

    default_password = default_password_from_phone(data.phone)

    user = User(
        name=data.name.strip(),
        email=data.email.lower().strip(),
        phone=data.phone,
        password_hash=hash_password(default_password),
        role=data.role,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.flush()
    return user, default_password


def update_user(db: Session, user_id: uuid.UUID, data: UserUpdate) -> User:
    user = db.get(User, user_id)
    if not user:
        raise UserServiceError("User not found")

    if data.email and data.email.lower() != user.email:
        if db.query(User).filter(User.email == data.email.lower(), User.id != user_id).first():
            raise UserServiceError("A user with this email already exists")
        user.email = data.email.lower().strip()

    if data.phone and data.phone != user.phone:
        if db.query(User).filter(User.phone == data.phone, User.id != user_id).first():
            raise UserServiceError("A user with this phone already exists")
        user.phone = data.phone

    if data.name:
        user.name = data.name.strip()
    if data.role:
        user.role = data.role
    if data.status:
        user.status = data.status

    db.add(user)
    db.flush()
    return user


def set_status(db: Session, user_id: uuid.UUID, status_value: UserStatus) -> User:
    user = db.get(User, user_id)
    if not user:
        raise UserServiceError("User not found")
    user.status = status_value
    db.add(user)
    db.flush()
    return user


def admin_reset_password(db: Session, user_id: uuid.UUID) -> tuple[User, str]:
    """Resets a user's password back to the last-6-digits-of-phone default."""
    user = db.get(User, user_id)
    if not user:
        raise UserServiceError("User not found")
    if not user.phone:
        raise UserServiceError("User has no phone number on file to derive a default password")

    new_password = default_password_from_phone(user.phone)
    user.password_hash = hash_password(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    db.add(user)
    db.flush()
    return user, new_password
