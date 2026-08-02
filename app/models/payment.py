import uuid
from datetime import date
from typing import Optional

from sqlalchemy import String, Date, Numeric, Enum as SAEnum, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import UUIDPKMixin, TimestampMixin
from app.models.enums import PaymentMethod, PaymentStatus


class Payment(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "payments"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True
    )

    amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(SAEnum(PaymentMethod, name="payment_method"), nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    transaction_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True, index=True)
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="payment_status"), nullable=False, default=PaymentStatus.PENDING
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Recorded by (for cash/bank/manual entries)
    recorded_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="payments")
    invoice: Mapped[Optional["Invoice"]] = relationship(back_populates="payments")
    ledger_entry: Mapped[Optional["LedgerEntry"]] = relationship(
        back_populates="payment", uselist=False, foreign_keys="LedgerEntry.payment_id"
    )
    payhero_transaction: Mapped[Optional["PayHeroTransaction"]] = relationship(
        back_populates="payment", uselist=False
    )
    receipt: Mapped[Optional["Receipt"]] = relationship(back_populates="payment", uselist=False)

    def __repr__(self) -> str:
        return f"<Payment {self.amount} {self.method} status={self.status}>"


class PayHeroTransaction(Base, UUIDPKMixin, TimestampMixin):
    """
    Raw request/response/callback log for every PayHero STK push attempt.
    This is what powers the Developer Section's Payment Debugging screen.
    """
    __tablename__ = "payhero_transactions"

    payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )

    checkout_request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True, index=True)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)

    request_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    response_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    callback_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="payhero_txn_status"), nullable=False, default=PaymentStatus.PENDING
    )
    error_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    payment: Mapped[Optional["Payment"]] = relationship(back_populates="payhero_transaction")

    def __repr__(self) -> str:
        return f"<PayHeroTransaction {self.checkout_request_id} status={self.status}>"


class Receipt(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "receipts"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    receipt_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    pdf_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    emailed_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    payment: Mapped["Payment"] = relationship(back_populates="receipt")

    def __repr__(self) -> str:
        return f"<Receipt {self.receipt_number}>"
