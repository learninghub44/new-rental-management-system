from datetime import date
from decimal import Decimal

from app.models.enums import InvoiceStatus, PaymentMethod, PaymentStatus
from app.models.payment import Payment
from app.schemas.billing import InvoiceCreate
from app.services.billing_service import create_invoice
from app.services.payment_service import allocate_payment
from app.services.ledger_service import get_tenant_balance


def _invoice_data(tenant_id, rent=Decimal("10000")):
    return InvoiceCreate(
        tenant_id=str(tenant_id),
        billing_period_start=date(2026, 1, 1),
        billing_period_end=date(2026, 1, 31),
        due_date=date(2026, 1, 5),
        rent=rent, water=Decimal("0"), electricity=Decimal("0"),
        service_charges=Decimal("0"), penalties=Decimal("0"), discounts=Decimal("0"),
    )


def _make_payment(db_session, tenant, amount, invoice_id=None):
    payment = Payment(
        tenant_id=tenant.id, invoice_id=invoice_id, amount=amount,
        method=PaymentMethod.CASH, status=PaymentStatus.SUCCESSFUL, payment_date=date.today(),
    )
    db_session.add(payment)
    db_session.flush()
    return payment


def test_full_payment_settles_invoice(db_session, make_tenant):
    tenant = make_tenant()
    invoice = create_invoice(db_session, _invoice_data(tenant.id))
    payment = _make_payment(db_session, tenant, Decimal("10000"), invoice.id)

    allocate_payment(db_session, payment)

    assert invoice.paid_amount == Decimal("10000")
    assert invoice.balance == Decimal("0")
    assert invoice.status == InvoiceStatus.PAID


def test_partial_payment_leaves_invoice_partially_paid(db_session, make_tenant):
    tenant = make_tenant()
    invoice = create_invoice(db_session, _invoice_data(tenant.id))
    payment = _make_payment(db_session, tenant, Decimal("4000"), invoice.id)

    allocate_payment(db_session, payment)

    assert invoice.paid_amount == Decimal("4000")
    assert invoice.balance == Decimal("6000")
    assert invoice.status == InvoiceStatus.PARTIALLY_PAID


def test_payment_without_invoice_applies_to_oldest_outstanding_first(db_session, make_tenant):
    tenant = make_tenant()
    older = create_invoice(db_session, _invoice_data(tenant.id, rent=Decimal("5000")))
    older.due_date = date(2026, 1, 1)
    newer = create_invoice(db_session, _invoice_data(tenant.id, rent=Decimal("5000")))
    newer.due_date = date(2026, 2, 1)
    db_session.flush()

    payment = _make_payment(db_session, tenant, Decimal("5000"))  # no invoice_id
    allocate_payment(db_session, payment)

    assert older.balance == Decimal("0")
    assert older.status == InvoiceStatus.PAID
    assert newer.balance == Decimal("5000")
    assert newer.status != InvoiceStatus.PAID


def test_overpayment_beyond_invoices_becomes_unallocated_credit(db_session, make_tenant):
    tenant = make_tenant()
    invoice = create_invoice(db_session, _invoice_data(tenant.id, rent=Decimal("5000")))
    payment = _make_payment(db_session, tenant, Decimal("7000"), invoice.id)

    allocate_payment(db_session, payment)

    assert invoice.balance == Decimal("0")
    assert invoice.status == InvoiceStatus.PAID
    # 5000 debit from the invoice, 7000 credit from the payment -> -2000 (credit balance)
    assert get_tenant_balance(db_session, tenant.id) == Decimal("-2000")


def test_payment_for_nonexistent_tenant_is_a_noop(db_session, make_tenant):
    """allocate_payment should not raise if the tenant lookup fails."""
    import uuid
    tenant = make_tenant()
    payment = Payment(
        tenant_id=uuid.uuid4(), amount=Decimal("100"), method=PaymentMethod.CASH,
        status=PaymentStatus.SUCCESSFUL, payment_date=date.today(),
    )
    db_session.add(payment)
    db_session.flush()
    allocate_payment(db_session, payment)  # should not raise
