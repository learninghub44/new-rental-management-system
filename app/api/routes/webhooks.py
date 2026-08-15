"""
Public, unauthenticated endpoints hit by third parties (PayHero's STK push
callback). No cookie/JWT session exists here — trust is established by a
shared secret we embedded in the callback URL we handed PayHero (see
_signed_callback_url() in payhero_service.py), not by the payload alone.
"""
import logging
import secrets

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.limiter import limiter
from app.services.payhero_service import handle_callback
from app.services.error_log import log_error

logger = logging.getLogger("rental_app.webhooks")
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/payhero")
@limiter.limit("30/minute")
async def payhero_callback(request: Request):
    if settings.PAYHERO_WEBHOOK_SECRET:
        provided = request.query_params.get("secret", "")
        if not secrets.compare_digest(provided, settings.PAYHERO_WEBHOOK_SECRET):
            logger.warning("Rejected PayHero callback with invalid/missing secret")
            # Still 200 so we don't leak which check failed and don't trigger
            # PayHero's retry storm for what is, from their side, a delivered call.
            return JSONResponse({"status": "rejected"}, status_code=200)
    else:
        logger.warning(
            "PAYHERO_WEBHOOK_SECRET is not set — payment callbacks are unauthenticated. "
            "Set this before accepting real payments."
        )

    payload = await request.json()
    db: Session = SessionLocal()
    try:
        txn = handle_callback(db, payload)
        db.commit()
    except Exception as exc:  # noqa: BLE001 — webhook must always ack, log and move on
        db.rollback()
        log_error(db, module="payhero_webhook", message="Failed to process PayHero callback", exc=exc)
        db.commit()
        logger.exception("PayHero callback processing failed")
        return JSONResponse({"status": "error"}, status_code=200)
    finally:
        db.close()

    if not txn:
        logger.warning("PayHero callback for unknown checkout_request_id: %s", payload)

    # Always 200 — PayHero retries on non-2xx, and we've already recorded whatever we could.
    return JSONResponse({"status": "received"})
