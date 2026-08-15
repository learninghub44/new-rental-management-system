from datetime import date
from decimal import Decimal

from app.models.enums import PaymentMethod, PaymentStatus
from app.models.payment import Payment, PayHeroTransaction
from app.services.payhero_service import handle_callback


def _make_pending_txn(db_session, tenant, amount=Decimal("1000"), checkout_id="chk-123"):
    payment = Payment(
        tenant_id=tenant.id, amount=amount, method=PaymentMethod.PAYHERO,
        status=PaymentStatus.PENDING, payment_date=date.today(),
    )
    db_session.add(payment)
    db_session.flush()

    txn = PayHeroTransaction(
        payment_id=payment.id, tenant_id=tenant.id, phone_number="254700000000",
        amount=amount, status=PaymentStatus.PENDING, checkout_request_id=checkout_id,
    )
    db_session.add(txn)
    db_session.flush()
    return payment, txn


def test_successful_callback_marks_payment_successful(db_session, make_tenant):
    tenant = make_tenant()
    payment, txn = _make_pending_txn(db_session, tenant)

    result = handle_callback(db_session, {
        "CheckoutRequestID": "chk-123", "status": "Success", "Amount": 1000,
        "MpesaReceiptNumber": "ABC123",
    })

    assert result.status == PaymentStatus.SUCCESSFUL
    assert payment.status == PaymentStatus.SUCCESSFUL


def test_unknown_checkout_id_is_ignored(db_session, make_tenant):
    tenant = make_tenant()
    _make_pending_txn(db_session, tenant)

    result = handle_callback(db_session, {"CheckoutRequestID": "does-not-exist", "status": "Success"})
    assert result is None


def test_callback_amount_mismatch_is_rejected(db_session, make_tenant):
    """A callback claiming a different amount than what we requested must not settle the payment."""
    tenant = make_tenant()
    payment, txn = _make_pending_txn(db_session, tenant, amount=Decimal("1000"))

    result = handle_callback(db_session, {
        "CheckoutRequestID": "chk-123", "status": "Success", "Amount": 1,  # tampered — 1 KES instead of 1000
    })

    assert result.status == PaymentStatus.FAILED
    assert payment.status == PaymentStatus.PENDING  # left untouched, not silently marked paid


def test_already_resolved_transaction_ignores_replayed_callback(db_session, make_tenant):
    """A second callback for an already-successful transaction must not double-process."""
    tenant = make_tenant()
    payment, txn = _make_pending_txn(db_session, tenant)
    handle_callback(db_session, {"CheckoutRequestID": "chk-123", "status": "Success", "Amount": 1000})
    assert payment.status == PaymentStatus.SUCCESSFUL

    # Replay with a "failed" status — should be ignored since txn is no longer PENDING.
    handle_callback(db_session, {"CheckoutRequestID": "chk-123", "status": "Failed"})
    assert payment.status == PaymentStatus.SUCCESSFUL


def test_failed_callback_marks_payment_failed(db_session, make_tenant):
    tenant = make_tenant()
    payment, txn = _make_pending_txn(db_session, tenant)

    handle_callback(db_session, {
        "CheckoutRequestID": "chk-123", "status": "Failed", "ResultDesc": "Insufficient funds",
    })

    assert payment.status == PaymentStatus.FAILED
