from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_tenant, require_staff
from app.core.templating import templates
from app.models.user import User
from app.models.tenant import Tenant
from app.models.payment import Payment
from app.models.billing import Invoice
from app.models.enums import PaymentStatus, InvoiceStatus

router = APIRouter(tags=["pages"])


@router.get("/")
def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login")


@router.get("/tenant/home")
def tenant_home(request: Request, db: Session = Depends(get_db), user: User = Depends(require_tenant)):
    from app.services.ledger_service import get_tenant_balance

    tenant = db.query(Tenant).filter(Tenant.user_id == user.id).first()
    balance = get_tenant_balance(db, tenant.id) if tenant else 0
    recent_payment = None
    next_invoice = None
    paid_this_month = Decimal("0")
    paid_this_year = Decimal("0")
    overdue_amount = Decimal("0")

    if tenant:
        recent_payment = (
            db.query(Payment)
            .filter(Payment.tenant_id == tenant.id, Payment.status == PaymentStatus.SUCCESSFUL)
            .order_by(Payment.payment_date.desc(), Payment.created_at.desc())
            .first()
        )

        today = date.today()

        # Next upcoming/overdue invoice due date — the earliest unpaid one.
        next_invoice = (
            db.query(Invoice)
            .filter(
                Invoice.tenant_id == tenant.id,
                Invoice.status.in_([InvoiceStatus.GENERATED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]),
            )
            .order_by(Invoice.due_date.asc())
            .first()
        )

        successful_payments = (
            db.query(Payment)
            .filter(Payment.tenant_id == tenant.id, Payment.status == PaymentStatus.SUCCESSFUL)
            .all()
        )
        for p in successful_payments:
            if p.payment_date.year == today.year:
                paid_this_year += p.amount
                if p.payment_date.month == today.month:
                    paid_this_month += p.amount

        overdue_invoices = (
            db.query(Invoice)
            .filter(Invoice.tenant_id == tenant.id, Invoice.status == InvoiceStatus.OVERDUE)
            .all()
        )
        overdue_amount = sum((inv.balance for inv in overdue_invoices), Decimal("0"))

    return templates.TemplateResponse(
        "tenant/home.html",
        {
            "request": request, "user": user, "tenant": tenant, "balance": balance,
            "recent_payment": recent_payment, "next_invoice": next_invoice,
            "paid_this_month": paid_this_month, "paid_this_year": paid_this_year,
            "overdue_amount": overdue_amount,
        },
    )


@router.get("/admin/dashboard")
def admin_dashboard(request: Request, user: User = Depends(require_staff)):
    return templates.TemplateResponse("admin/dashboard.html", {"request": request, "user": user})


@router.get("/admin/more")
def admin_more(request: Request, user: User = Depends(require_staff)):
    return templates.TemplateResponse("admin/more.html", {"request": request, "user": user})
