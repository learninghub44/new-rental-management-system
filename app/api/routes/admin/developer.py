from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.templating import templates
from app.core.config import settings
from app.models.user import User
from app.models.system import ErrorLog, ActivityLog, EmailLog
from app.models.payment import PayHeroTransaction
from app.models.enums import ErrorLogStatus, EmailStatus

router = APIRouter(prefix="/admin/developer", tags=["admin-developer"])


@router.get("")
def developer_index(request: Request, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    open_errors = db.query(ErrorLog).filter(ErrorLog.status == ErrorLogStatus.OPEN).count()
    failed_emails = db.query(EmailLog).filter(EmailLog.status == EmailStatus.FAILED).count()
    payhero_configured = bool(settings.PAYHERO_API_USERNAME and settings.PAYHERO_CHANNEL_ID)

    return templates.TemplateResponse(
        "admin/developer/index.html",
        {"request": request, "user": user, "db_ok": db_ok, "open_errors": open_errors,
         "failed_emails": failed_emails, "payhero_configured": payhero_configured, "environment": settings.ENVIRONMENT},
    )


@router.get("/errors")
def developer_errors(request: Request, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    errors = db.query(ErrorLog).order_by(ErrorLog.created_at.desc()).limit(100).all()
    return templates.TemplateResponse("admin/developer/errors.html", {"request": request, "user": user, "errors": errors})


@router.get("/activity")
def developer_activity(request: Request, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    entries = db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(150).all()
    return templates.TemplateResponse("admin/developer/activity.html", {"request": request, "user": user, "entries": entries})


@router.get("/emails")
def developer_emails(request: Request, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    emails = db.query(EmailLog).order_by(EmailLog.created_at.desc()).limit(100).all()
    return templates.TemplateResponse("admin/developer/emails.html", {"request": request, "user": user, "emails": emails})


@router.get("/payments")
def developer_payments(request: Request, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    transactions = db.query(PayHeroTransaction).order_by(PayHeroTransaction.created_at.desc()).limit(100).all()
    return templates.TemplateResponse("admin/developer/payments.html", {"request": request, "user": user, "transactions": transactions})
