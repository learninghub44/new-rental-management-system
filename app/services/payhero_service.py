"""
PayHero (M-Pesa STK push) integration. Every attempt — request, response,
and eventual callback — is logged to PayHeroTransaction, which is what
powers the Developer Section's payment debugging screen.
"""
import base64
import uuid
from datetime import date
from typing import Optional
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.payment import Payment, PayHeroTransaction
from app.models.tenant import Tenant
from app.models.enums import PaymentMethod, PaymentStatus
from app.schemas.payment import STKPushRequest


class PayHeroServiceError(Exception):
    pass


def _basic_auth_header() -> str:
    raw = f"{settings.PAYHERO_API_USERNAME}:{settings.PAYHERO_API_PASSWORD}".encode()
    return f"Basic {base64.b64encode(raw).decode()}"


def _signed_callback_url() -> str:
    """
    PayHero's callback payload has no signature we can verify against, so we
    embed PAYHERO_WEBHOOK_SECRET as a query param on the callback URL we hand
    PayHero at request time. The webhook handler then requires that same
    secret on the inbound call — see app/api/routes/webhooks.py. Without a
    configured secret, callers can't be distinguished from anyone who
    guesses/observes a checkout_request_id.
    """
    base = settings.PAYHERO_CALLBACK_URL
    if not settings.PAYHERO_WEBHOOK_SECRET or not base:
        return base
    parsed = urlparse(base)
    query = dict(parse_qsl(parsed.query))
    query["secret"] = settings.PAYHERO_WEBHOOK_SECRET
    return urlunparse(parsed._replace(query=urlencode(query)))


def initiate_stk_push(db: Session, tenant: Tenant, data: STKPushRequest) -> PayHeroTransaction:
    invoice_id = uuid.UUID(data.invoice_id) if data.invoice_id else None

    payment = Payment(
        tenant_id=tenant.id,
        invoice_id=invoice_id,
        amount=data.amount,
        method=PaymentMethod.PAYHERO,
        status=PaymentStatus.PENDING,
        payment_date=date.today(),
    )
    db.add(payment)
    db.flush()

    txn = PayHeroTransaction(
        payment_id=payment.id,
        tenant_id=tenant.id,
        phone_number=data.phone_number,
        amount=data.amount,
        status=PaymentStatus.PENDING,
    )
    db.add(txn)
    db.flush()

    request_payload = {
        "amount": float(data.amount),
        "phone_number": data.phone_number,
        "channel_id": settings.PAYHERO_CHANNEL_ID,
        "provider": "m-pesa",
        "external_reference": str(payment.id),
        "callback_url": _signed_callback_url(),
    }
    txn.request_payload = request_payload

    if not settings.PAYHERO_API_USERNAME or not settings.PAYHERO_CHANNEL_ID:
        txn.status = PaymentStatus.FAILED
        txn.error_reason = "PayHero is not configured (missing API credentials or channel ID)"
        payment.status = PaymentStatus.FAILED
        db.add_all([txn, payment])
        db.flush()
        return txn

    try:
        response = httpx.post(
            f"{settings.PAYHERO_BASE_URL}/payments",
            json=request_payload,
            headers={"Authorization": _basic_auth_header(), "Content-Type": "application/json"},
            timeout=30.0,
        )
        response_data = response.json() if response.content else {}
        txn.response_payload = response_data

        checkout_id = response_data.get("CheckoutRequestID") or response_data.get("reference")
        if response.status_code in (200, 201) and checkout_id:
            txn.checkout_request_id = str(checkout_id)
        else:
            txn.status = PaymentStatus.FAILED
            txn.error_reason = f"HTTP {response.status_code}: {response.text[:300]}"
            payment.status = PaymentStatus.FAILED
    except Exception as exc:  # noqa: BLE001 — always log, never crash the request flow
        txn.status = PaymentStatus.FAILED
        txn.error_reason = str(exc)[:500]
        payment.status = PaymentStatus.FAILED

    db.add_all([txn, payment])
    db.flush()
    return txn


def handle_callback(db: Session, payload: dict) -> Optional[PayHeroTransaction]:
    """
    Reconciles PayHero's async webhook against the pending transaction it
    refers to. Caller (app/api/routes/webhooks.py) is responsible for
    rejecting requests that don't carry the shared secret before this runs.
    """
    checkout_id = (
        payload.get("CheckoutRequestID")
        or payload.get("checkout_request_id")
        or payload.get("reference")
    )
    if not checkout_id:
        return None

    txn = db.query(PayHeroTransaction).filter(PayHeroTransaction.checkout_request_id == str(checkout_id)).first()
    if not txn:
        return None

    # Only a still-pending transaction can be settled by a callback — blocks
    # replays/duplicates from flipping an already-resolved transaction again.
    if txn.status != PaymentStatus.PENDING:
        return txn

    # Sanity-check the amount the callback claims against what we actually
    # requested. A mismatch means the payload doesn't correspond to the
    # transaction we initiated, even if the checkout_request_id matches.
    callback_amount = payload.get("Amount") or payload.get("amount")
    if callback_amount is not None:
        try:
            from decimal import Decimal
            if Decimal(str(callback_amount)) != Decimal(str(txn.amount)):
                txn.status = PaymentStatus.FAILED
                txn.error_reason = "Callback amount did not match the requested amount"
                txn.callback_payload = payload
                db.add(txn)
                db.flush()
                return txn
        except Exception:
            pass

    txn.callback_payload = payload
    result_indicator = str(payload.get("status") or payload.get("ResultCode") or "").strip().lower()
    success = result_indicator in ("success", "successful", "0", "completed", "true")

    payment = db.get(Payment, txn.payment_id) if txn.payment_id else None

    if success:
        txn.status = PaymentStatus.SUCCESSFUL
        if payment and payment.status != PaymentStatus.SUCCESSFUL:
            payment.status = PaymentStatus.SUCCESSFUL
            payment.transaction_id = (
                payload.get("MpesaReceiptNumber") or payload.get("transaction_id") or str(checkout_id)
            )
            db.add(payment)
            db.flush()

            from app.services.payment_service import allocate_payment
            from app.services.receipt_service import generate_receipt

            allocate_payment(db, payment)
            generate_receipt(db, payment)
    else:
        txn.status = PaymentStatus.FAILED
        txn.error_reason = payload.get("ResultDesc") or payload.get("message") or "Payment failed"
        if payment:
            payment.status = PaymentStatus.FAILED
            db.add(payment)

    db.add(txn)
    db.flush()
    return txn
