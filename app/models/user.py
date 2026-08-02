import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Enum as SAEnum, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import UUIDPKMixin, TimestampMixin
from app.models.enums import UserRole, UserStatus


class User(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole, name="user_role"), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus, name="user_status"), nullable=False, default=UserStatus.ACTIVE
    )

    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Optional link: if this user IS a tenant, points to their tenant profile
    tenant_profile: Mapped[Optional["Tenant"]] = relationship(
        back_populates="user", uselist=False, foreign_keys="Tenant.user_id"
    )

    # Optional link: caretakers are assigned to properties they manage
    managed_properties: Mapped[list["Property"]] = relationship(
        back_populates="manager", foreign_keys="Property.manager_id"
    )

    login_history: Mapped[list["LoginHistory"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"


class LoginHistory(Base, UUIDPKMixin):
    __tablename__ = "login_history"

    # Nullable: failed attempts against an email that doesn't exist have no known user.
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    attempted_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    successful: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[Optional["User"]] = relationship(back_populates="login_history")


class PasswordResetToken(Base, UUIDPKMixin):
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
