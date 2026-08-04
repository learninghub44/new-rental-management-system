"""
Public, unauthenticated endpoints hit by third parties (PayHero's STK push
callback). No cookie/JWT session exists here — trust is established by the
payload referencing a checkout_request_id we already issued.
"""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.services.payhero_service import handle_callback
from app.services.error_log import log_error

logger = logging.getLogger("rental_app.webhooks")
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/payhero")
async def payhero_callback(request: Request):
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
