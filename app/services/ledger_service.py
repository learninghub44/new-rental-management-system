"""
Shared helpers for writing to the append-only ledger. Every invoice,
payment, penalty, discount, and adjustment must go through
post_ledger_entry() so the ledger stays the single source of truth for a
tenant's balance (see PRD section 12 / app/models/billing.py).
"""
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.billing import LedgerEntry
from app.models.tenant import Tenant
from app.models.enums import LedgerTransactionType


def get_tenant_balance(db: Session, tenant_id: uuid.UUID) -> Decimal:
    """Current outstanding balance = sum(debits) - sum(credits). Positive = tenant owes money."""
    debit_total = db.query(func.coalesce(func.sum(LedgerEntry.debit), 0)).filter(LedgerEntry.tenant_id == tenant_id).scalar()
    credit_total = db.query(func.coalesce(func.sum(LedgerEntry.credit), 0)).filter(LedgerEntry.tenant_id == tenant_id).scalar()
    return Decimal(debit_total) - Decimal(credit_total)


def post_ledger_entry(
    db: Session,
    tenant: Tenant,
    transaction_type: LedgerTransactionType,
    description: str,
    debit: Decimal = Decimal("0"),
    credit: Decimal = Decimal("0"),
    invoice_id: Optional[uuid.UUID] = None,
    payment_id: Optional[uuid.UUID] = None,
    reference: Optional[str] = None,
    transaction_date: Optional[date] = None,
) -> LedgerEntry:
    previous_balance = get_tenant_balance(db, tenant.id)
    running_balance = previous_balance + debit - credit

    entry = LedgerEntry(
        tenant_id=tenant.id,
        invoice_id=invoice_id,
        payment_id=payment_id,
        transaction_type=transaction_type,
        description=description,
        debit=debit,
        credit=credit,
        running_balance=running_balance,
        reference=reference,
        transaction_date=transaction_date or date.today(),
    )
    db.add(entry)
    db.flush()
    return entry
