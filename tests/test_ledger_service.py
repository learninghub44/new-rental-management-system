from decimal import Decimal

from app.models.enums import LedgerTransactionType
from app.services.ledger_service import get_tenant_balance, post_ledger_entry


def test_balance_starts_at_zero(db_session, make_tenant):
    tenant = make_tenant()
    assert get_tenant_balance(db_session, tenant.id) == Decimal("0")


def test_debit_increases_balance(db_session, make_tenant):
    tenant = make_tenant()
    post_ledger_entry(
        db_session, tenant, LedgerTransactionType.INVOICE,
        description="Rent invoice", debit=Decimal("5000"),
    )
    assert get_tenant_balance(db_session, tenant.id) == Decimal("5000")


def test_credit_decreases_balance(db_session, make_tenant):
    tenant = make_tenant()
    post_ledger_entry(db_session, tenant, LedgerTransactionType.INVOICE, "Invoice", debit=Decimal("5000"))
    post_ledger_entry(db_session, tenant, LedgerTransactionType.PAYMENT, "Payment", credit=Decimal("2000"))
    assert get_tenant_balance(db_session, tenant.id) == Decimal("3000")


def test_running_balance_is_recorded_on_the_entry(db_session, make_tenant):
    tenant = make_tenant()
    e1 = post_ledger_entry(db_session, tenant, LedgerTransactionType.INVOICE, "Invoice 1", debit=Decimal("1000"))
    e2 = post_ledger_entry(db_session, tenant, LedgerTransactionType.PAYMENT, "Payment 1", credit=Decimal("400"))
    assert e1.running_balance == Decimal("1000")
    assert e2.running_balance == Decimal("600")


def test_ledger_entries_are_isolated_per_tenant(db_session, make_tenant):
    tenant_a = make_tenant(phone="0700000001", national_id="A1")
    tenant_b = make_tenant(phone="0700000002", national_id="B1")
    post_ledger_entry(db_session, tenant_a, LedgerTransactionType.INVOICE, "A invoice", debit=Decimal("1000"))
    assert get_tenant_balance(db_session, tenant_a.id) == Decimal("1000")
    assert get_tenant_balance(db_session, tenant_b.id) == Decimal("0")


def test_balance_can_go_negative_for_overpayment(db_session, make_tenant):
    """A credit balance (tenant overpaid) is represented as a negative balance."""
    tenant = make_tenant()
    post_ledger_entry(db_session, tenant, LedgerTransactionType.PAYMENT, "Overpayment", credit=Decimal("500"))
    assert get_tenant_balance(db_session, tenant.id) == Decimal("-500")
