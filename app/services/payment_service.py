"""
Payment recording (manual: cash/bank) and allocation against invoices.
PayHero (M-Pesa STK push) payments are created in payhero_service.py but
land here too, via allocate_payment(), once the callback confirms success.
"""
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.billing import Invoice
from app.models.payment import Payment
from app.models.tenant import Tenant
from app.models.enums import InvoiceStatus, LedgerTransactionType, PaymentStatus
from app.schemas.payment import ManualPaymentCreate
from app.services.billing_service import recalc_invoice_status
from app.services.ledger_service import post_ledger_entry


class PaymentServiceError(Exception):
    pass


def allocate_payment(db: Session, payment: Payment) -> None:
    """
    Applies a successful payment to the invoice it was made against (or, if
    none was specified, to the tenant's oldest outstanding invoices
    first). Any amount left over after every outstanding invoice is settled
    is posted as a standalone ledger credit (a running credit balance).
    """
    tenant = db.get(Tenant, payment.tenant_id)
    if not tenant:
        return

    remaining = payment.amount

    if payment.invoice_id:
        target = db.get(Invoice, payment.invoice_id)
        invoices = [target] if target else []
    else:
        invoices = (
            db.query(Invoice)
            .filter(
                Invoice.tenant_id == tenant.id,
                Invoice.status.in_([InvoiceStatus.GENERATED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]),
            )
            .order_by(Invoice.due_date.asc())
            .all()
        )

    for invoice in invoices:
        if remaining <= 0:
            break
        applied = min(remaining, invoice.balance)
        if applied <= 0:
            continue
        invoice.paid_amount += applied
        invoice.balance -= applied
        recalc_invoice_status(invoice)
        db.add(invoice)
        remaining -= applied

        post_ledger_entry(
            db, tenant, LedgerTransactionType.PAYMENT,
            description=f"Payment {payment.reference or str(payment.id)[:8]} applied to {invoice.invoice_number}",
            credit=applied, invoice_id=invoice.id, payment_id=payment.id, transaction_date=payment.payment_date,
        )

    if remaining > 0:
        post_ledger_entry(
            db, tenant, LedgerTransactionType.PAYMENT,
            description=f"Payment {payment.reference or str(payment.id)[:8]} (unallocated credit)",
            credit=remaining, payment_id=payment.id, transaction_date=payment.payment_date,
        )


def record_manual_payment(db: Session, data: ManualPaymentCreate, recorded_by_user_id: uuid.UUID) -> Payment:
    tenant = db.get(Tenant, uuid.UUID(data.tenant_id))
    if not tenant:
        raise PaymentServiceError("Tenant not found")

    invoice_id = None
    if data.invoice_id:
        invoice_id = uuid.UUID(data.invoice_id)
        if not db.get(Invoice, invoice_id):
            raise PaymentServiceError("Invoice not found")

    payment = Payment(
        tenant_id=tenant.id,
        invoice_id=invoice_id,
        amount=data.amount,
        method=data.method,
        reference=data.reference,
        status=PaymentStatus.SUCCESSFUL,
        payment_date=data.payment_date,
        recorded_by_user_id=recorded_by_user_id,
    )
    db.add(payment)
    db.flush()

    allocate_payment(db, payment)

    from app.services.receipt_service import generate_receipt
    generate_receipt(db, payment)

    return payment


def list_payments(
    db: Session, tenant_id: Optional[uuid.UUID] = None, page: int = 1, page_size: int = 20,
) -> tuple[list[Payment], int]:
    query = db.query(Payment)
    if tenant_id:
        query = query.filter(Payment.tenant_id == tenant_id)
    total = query.count()
    items = query.order_by(Payment.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return items, total
