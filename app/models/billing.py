import uuid
from datetime import date
from typing import Optional

from sqlalchemy import String, Date, Numeric, Enum as SAEnum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import UUIDPKMixin, TimestampMixin
from app.models.enums import InvoiceStatus, LedgerTransactionType


class Invoice(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "invoices"

    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lease_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leases.id", ondelete="SET NULL"), nullable=True
    )

    billing_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    billing_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    rent: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    water: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    electricity: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    service_charges: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    penalties: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    discounts: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    total_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    paid_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    balance: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    status: Mapped[InvoiceStatus] = mapped_column(
        SAEnum(InvoiceStatus, name="invoice_status"), nullable=False, default=InvoiceStatus.DRAFT
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="invoices")
    payments: Mapped[list["Payment"]] = relationship(back_populates="invoice")
    ledger_entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="invoice")

    def __repr__(self) -> str:
        return f"<Invoice {self.invoice_number} status={self.status}>"


class LedgerEntry(Base, UUIDPKMixin):
    """
    Append-only financial log. This is the single source of truth for a
    tenant's balance — balances are always derived by summing this table,
    never stored/edited directly on the Tenant record (see PRD section 12).
    """
    __tablename__ = "ledger_entries"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )
    payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True
    )

    transaction_type: Mapped[LedgerTransactionType] = mapped_column(
        SAEnum(LedgerTransactionType, name="ledger_transaction_type"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    debit: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    credit: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    running_balance: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="ledger_entries")
    invoice: Mapped[Optional["Invoice"]] = relationship(back_populates="ledger_entries")
    payment: Mapped[Optional["Payment"]] = relationship(back_populates="ledger_entry", foreign_keys=[payment_id])

    def __repr__(self) -> str:
        return f"<LedgerEntry {self.transaction_type} tenant={self.tenant_id} balance={self.running_balance}>"
