import uuid
from typing import Optional

from sqlalchemy import String, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import UUIDPKMixin, TimestampMixin
from app.models.enums import ActivityAction, ErrorLogStatus, EmailStatus


class ErrorLog(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "error_logs"

    module: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    stack_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[ErrorLogStatus] = mapped_column(
        SAEnum(ErrorLogStatus, name="error_log_status"), nullable=False, default=ErrorLogStatus.OPEN
    )

    def __repr__(self) -> str:
        return f"<ErrorLog {self.module}: {self.message[:50]}>"


class ActivityLog(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "activity_logs"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[ActivityAction] = mapped_column(SAEnum(ActivityAction, name="activity_action"), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    def __repr__(self) -> str:
        return f"<ActivityLog {self.action} by {self.user_id}>"


class EmailLog(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "email_logs"

    recipient: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    template_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[EmailStatus] = mapped_column(
        SAEnum(EmailStatus, name="email_status"), nullable=False, default=EmailStatus.QUEUED
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<EmailLog to={self.recipient} status={self.status}>"
