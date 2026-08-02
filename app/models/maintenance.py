import uuid
from typing import Optional

from sqlalchemy import String, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import UUIDPKMixin, TimestampMixin
from app.models.enums import MaintenancePriority, MaintenanceStatus


class MaintenanceRequest(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "maintenance_requests"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    priority: Mapped[MaintenancePriority] = mapped_column(
        SAEnum(MaintenancePriority, name="maintenance_priority"), nullable=False, default=MaintenancePriority.MEDIUM
    )
    status: Mapped[MaintenanceStatus] = mapped_column(
        SAEnum(MaintenanceStatus, name="maintenance_status"), nullable=False, default=MaintenanceStatus.SUBMITTED
    )
    assigned_to_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="maintenance_requests")

    def __repr__(self) -> str:
        return f"<MaintenanceRequest {self.title} status={self.status}>"
