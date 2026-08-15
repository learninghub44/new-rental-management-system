from datetime import date, timedelta
from decimal import Decimal

from app.models.enums import InvoiceStatus
from app.schemas.billing import InvoiceCreate, InvoiceAdjust
from app.services.billing_service import (
    create_invoice, adjust_invoice, cancel_invoice, recalc_invoice_status, refresh_overdue_statuses,
)
from app.services.ledger_service import get_tenant_balance


def _invoice_data(tenant_id, **overrides):
    defaults = dict(
        tenant_id=str(tenant_id),
        billing_period_start=date(2026, 1, 1),
        billing_period_end=date(2026, 1, 31),
        due_date=date(2026, 1, 5),
        rent=Decimal("10000"),
        water=Decimal("500"),
        electricity=Decimal("300"),
        service_charges=Decimal("200"),
        penalties=Decimal("0"),
        discounts=Decimal("0"),
    )
    defaults.update(overrides)
    return InvoiceCreate(**defaults)


def test_create_invoice_totals_are_summed_correctly(db_session, make_tenant):
    tenant = make_tenant()
    invoice = create_invoice(db_session, _invoice_data(tenant.id))
    assert invoice.total_amount == Decimal("11000")
    assert invoice.balance == Decimal("11000")
    assert invoice.paid_amount == Decimal("0")


def test_create_invoice_posts_a_matching_ledger_debit(db_session, make_tenant):
    tenant = make_tenant()
    invoice = create_invoice(db_session, _invoice_data(tenant.id))
    assert get_tenant_balance(db_session, tenant.id) == invoice.total_amount


def test_discounts_reduce_the_total(db_session, make_tenant):
    tenant = make_tenant()
    invoice = create_invoice(db_session, _invoice_data(tenant.id, discounts=Decimal("1000")))
    assert invoice.total_amount == Decimal("10000")


def test_invoice_number_increments_within_the_month(db_session, make_tenant):
    tenant = make_tenant()
    inv1 = create_invoice(db_session, _invoice_data(tenant.id))
    inv2 = create_invoice(db_session, _invoice_data(tenant.id))
    assert inv1.invoice_number != inv2.invoice_number


def test_recalc_status_generated_when_unpaid_and_not_due(db_session, make_tenant):
    tenant = make_tenant()
    invoice = create_invoice(db_session, _invoice_data(tenant.id, due_date=date.today() + timedelta(days=10)))
    assert invoice.status == InvoiceStatus.GENERATED


def test_recalc_status_overdue_when_past_due_date(db_session, make_tenant):
    tenant = make_tenant()
    invoice = create_invoice(db_session, _invoice_data(tenant.id, due_date=date.today() - timedelta(days=1)))
    assert invoice.status == InvoiceStatus.OVERDUE


def test_recalc_status_paid_when_fully_settled(db_session, make_tenant):
    tenant = make_tenant()
    invoice = create_invoice(db_session, _invoice_data(tenant.id))
    invoice.paid_amount = invoice.total_amount
    recalc_invoice_status(invoice)
    assert invoice.status == InvoiceStatus.PAID


def test_adjust_invoice_penalty_increases_balance_and_ledger(db_session, make_tenant):
    tenant = make_tenant()
    invoice = create_invoice(db_session, _invoice_data(tenant.id))
    original_total = invoice.total_amount
    adjust_invoice(db_session, invoice.id, InvoiceAdjust(penalties=Decimal("300")))
    assert invoice.total_amount == original_total + Decimal("300")
    assert invoice.balance == original_total + Decimal("300")
    assert get_tenant_balance(db_session, tenant.id) == invoice.total_amount


def test_adjust_invoice_discount_decreases_balance(db_session, make_tenant):
    tenant = make_tenant()
    invoice = create_invoice(db_session, _invoice_data(tenant.id))
    original_total = invoice.total_amount
    adjust_invoice(db_session, invoice.id, InvoiceAdjust(discounts=Decimal("500")))
    assert invoice.total_amount == original_total - Decimal("500")


def test_cancel_invoice_writes_off_remaining_balance(db_session, make_tenant):
    tenant = make_tenant()
    invoice = create_invoice(db_session, _invoice_data(tenant.id))
    cancel_invoice(db_session, invoice.id)
    assert invoice.status == InvoiceStatus.CANCELLED
    assert invoice.balance == Decimal("0")
    # The debit from creation should be fully offset by the cancellation credit.
    assert get_tenant_balance(db_session, tenant.id) == Decimal("0")


def test_refresh_overdue_statuses_flips_generated_invoices(db_session, make_tenant):
    tenant = make_tenant()
    # Create while still due in the future (GENERATED), then simulate time
    # passing by moving the due date back without going through recalc —
    # this is what refresh_overdue_statuses is meant to catch on a schedule.
    invoice = create_invoice(db_session, _invoice_data(tenant.id, due_date=date.today() + timedelta(days=1)))
    assert invoice.status == InvoiceStatus.GENERATED
    invoice.due_date = date.today() - timedelta(days=2)
    db_session.add(invoice)
    db_session.flush()

    flipped = refresh_overdue_statuses(db_session)
    assert flipped == 1
    assert invoice.status == InvoiceStatus.OVERDUE
