import uuid
from datetime import date
from typing import Optional

from sqlalchemy import String, Date, Numeric, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import UUIDPKMixin, TimestampMixin
from app.models.enums import TenantStatus, LeaseStatus


class Tenant(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "tenants"

    # Optional: tenant may or may not have a login account
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True
    )

    full_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    national_id: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Current assignment (denormalized for quick lookup; source of truth is the active Lease)
    property_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="SET NULL"), nullable=True
    )
    unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units.id", ondelete="SET NULL"), nullable=True
    )
    move_in_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    monthly_rent: Mapped[Optional[Numeric]] = mapped_column(Numeric(12, 2), nullable=True)
    deposit: Mapped[Optional[Numeric]] = mapped_column(Numeric(12, 2), nullable=True)

    status: Mapped[TenantStatus] = mapped_column(
        SAEnum(TenantStatus, name="tenant_status"), nullable=False, default=TenantStatus.ACTIVE
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="tenant_profile", foreign_keys=[user_id])
    leases: Mapped[list["Lease"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="tenant")
    ledger_entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="tenant")
    payments: Mapped[list["Payment"]] = relationship(back_populates="tenant")
    maintenance_requests: Mapped[list["MaintenanceRequest"]] = relationship(back_populates="tenant")

    def __repr__(self) -> str:
        return f"<Tenant {self.full_name}>"


class Lease(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "leases"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    rent_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    deposit: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    agreement_document_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[LeaseStatus] = mapped_column(
        SAEnum(LeaseStatus, name="lease_status"), nullable=False, default=LeaseStatus.ACTIVE
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="leases")
    unit: Mapped["Unit"] = relationship(back_populates="leases")

    def __repr__(self) -> str:
        return f"<Lease tenant={self.tenant_id} unit={self.unit_id} status={self.status}>"
