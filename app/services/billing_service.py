"""
Invoice generation. Charges (rent/water/electricity/service charges/penalties/
discounts) are always set by an admin — either one-off via create_invoice(),
or in bulk every month via generate_monthly_invoices(), which bills every
tenant on an active lease their lease's rent amount plus the admin-supplied
utility/service figures for that billing cycle.
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.billing import Invoice
from app.models.tenant import Tenant, Lease
from app.models.enums import InvoiceStatus, LeaseStatus, LedgerTransactionType
from app.schemas.billing import InvoiceCreate, InvoiceAdjust, MonthlyGenerateRequest
from app.services.ledger_service import post_ledger_entry


class BillingServiceError(Exception):
    pass


def _next_invoice_number(db: Session) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m")
    count_this_month = (
        db.query(Invoice)
        .filter(Invoice.invoice_number.like(f"INV-{stamp}-%"))
        .count()
    )
    return f"INV-{stamp}-{count_this_month + 1:04d}"


def _compute_total(rent: Decimal, water: Decimal, electricity: Decimal, service_charges: Decimal, penalties: Decimal, discounts: Decimal) -> Decimal:
    return (rent + water + electricity + service_charges + penalties) - discounts


def recalc_invoice_status(invoice: Invoice) -> None:
    if invoice.status == InvoiceStatus.CANCELLED:
        return
    if invoice.paid_amount >= invoice.total_amount and invoice.total_amount > 0:
        invoice.status = InvoiceStatus.PAID
    elif invoice.paid_amount > 0:
        invoice.status = InvoiceStatus.PARTIALLY_PAID
    elif invoice.due_date < date.today():
        invoice.status = InvoiceStatus.OVERDUE
    else:
        invoice.status = InvoiceStatus.GENERATED


def create_invoice(db: Session, data: InvoiceCreate) -> Invoice:
    tenant = db.get(Tenant, uuid.UUID(data.tenant_id))
    if not tenant:
        raise BillingServiceError("Tenant not found")

    lease_id = uuid.UUID(data.lease_id) if data.lease_id else None
    total = _compute_total(data.rent, data.water, data.electricity, data.service_charges, data.penalties, data.discounts)

    invoice = Invoice(
        invoice_number=_next_invoice_number(db),
        tenant_id=tenant.id,
        lease_id=lease_id,
        billing_period_start=data.billing_period_start,
        billing_period_end=data.billing_period_end,
        due_date=data.due_date,
        rent=data.rent,
        water=data.water,
        electricity=data.electricity,
        service_charges=data.service_charges,
        penalties=data.penalties,
        discounts=data.discounts,
        total_amount=total,
        paid_amount=Decimal("0"),
        balance=total,
        notes=data.notes,
    )
    recalc_invoice_status(invoice)
    db.add(invoice)
    db.flush()

    post_ledger_entry(
        db, tenant, LedgerTransactionType.INVOICE,
        description=f"Invoice {invoice.invoice_number} ({data.billing_period_start:%b %Y})",
        debit=total, invoice_id=invoice.id, transaction_date=date.today(),
    )
    return invoice


def generate_monthly_invoices(db: Session, data: MonthlyGenerateRequest) -> list[Invoice]:
    """
    Bills every tenant with an active lease for the given period. Rent comes
    from the lease; water/electricity/service charges are set by the admin
    for the whole run (per-tenant amounts can still be adjusted afterward via
    adjust_invoice). Leases already billed for this exact period are skipped,
    so this is safe to re-run.
    """
    active_leases = db.query(Lease).filter(Lease.status == LeaseStatus.ACTIVE).all()
    created: list[Invoice] = []

    for lease in active_leases:
        already_billed = (
            db.query(Invoice)
            .filter(Invoice.lease_id == lease.id, Invoice.billing_period_start == data.billing_period_start)
            .first()
        )
        if already_billed:
            continue

        invoice_data = InvoiceCreate(
            tenant_id=str(lease.tenant_id),
            lease_id=str(lease.id),
            billing_period_start=data.billing_period_start,
            billing_period_end=data.billing_period_end,
            due_date=data.due_date,
            rent=lease.rent_amount,
            water=data.water,
            electricity=data.electricity,
            service_charges=data.service_charges,
            penalties=Decimal("0"),
            discounts=Decimal("0"),
            notes="Monthly billing (auto-generated)",
        )
        created.append(create_invoice(db, invoice_data))

    return created


def adjust_invoice(db: Session, invoice_id: uuid.UUID, data: InvoiceAdjust) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise BillingServiceError("Invoice not found")
    if invoice.status == InvoiceStatus.CANCELLED:
        raise BillingServiceError("Cannot adjust a cancelled invoice")

    tenant = db.get(Tenant, invoice.tenant_id)
    delta = Decimal("0")

    if data.penalties is not None:
        delta += data.penalties - invoice.penalties
        invoice.penalties = data.penalties
    if data.discounts is not None:
        delta -= data.discounts - invoice.discounts
        invoice.discounts = data.discounts
    if data.notes is not None:
        invoice.notes = data.notes

    if delta != 0:
        invoice.total_amount += delta
        invoice.balance += delta
        recalc_invoice_status(invoice)
        post_ledger_entry(
            db, tenant, LedgerTransactionType.ADJUSTMENT,
            description=f"Adjustment on {invoice.invoice_number}",
            debit=delta if delta > 0 else Decimal("0"),
            credit=-delta if delta < 0 else Decimal("0"),
            invoice_id=invoice.id, transaction_date=date.today(),
        )

    db.add(invoice)
    db.flush()
    return invoice


def cancel_invoice(db: Session, invoice_id: uuid.UUID) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise BillingServiceError("Invoice not found")
    if invoice.status == InvoiceStatus.PAID:
        raise BillingServiceError("Cannot cancel a fully paid invoice")

    tenant = db.get(Tenant, invoice.tenant_id)
    remaining = invoice.balance
    if remaining > 0:
        post_ledger_entry(
            db, tenant, LedgerTransactionType.ADJUSTMENT,
            description=f"Cancelled {invoice.invoice_number} — balance written off",
            credit=remaining, invoice_id=invoice.id, transaction_date=date.today(),
        )
    invoice.balance = Decimal("0")
    invoice.status = InvoiceStatus.CANCELLED
    db.add(invoice)
    db.flush()
    return invoice


def list_invoices(
    db: Session, tenant_id: Optional[uuid.UUID] = None, status_filter: Optional[InvoiceStatus] = None,
    page: int = 1, page_size: int = 20,
) -> tuple[list[Invoice], int]:
    query = db.query(Invoice)
    if tenant_id:
        query = query.filter(Invoice.tenant_id == tenant_id)
    if status_filter:
        query = query.filter(Invoice.status == status_filter)

    total = query.count()
    items = query.order_by(Invoice.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def refresh_overdue_statuses(db: Session) -> int:
    """Flips GENERATED/PARTIALLY_PAID invoices past their due date to OVERDUE. Safe to call on a schedule."""
    stale = (
        db.query(Invoice)
        .filter(Invoice.status.in_([InvoiceStatus.GENERATED, InvoiceStatus.PARTIALLY_PAID]), Invoice.due_date < date.today())
        .all()
    )
    for invoice in stale:
        invoice.status = InvoiceStatus.OVERDUE
        db.add(invoice)
    db.flush()
    return len(stale)
