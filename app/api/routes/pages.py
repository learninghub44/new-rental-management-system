from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_tenant, require_staff
from app.core.templating import templates
from app.models.user import User
from app.models.tenant import Tenant
from app.models.payment import Payment
from app.models.billing import Invoice
from app.models.property import Property, Unit
from app.models.maintenance import MaintenanceRequest
from app.models.enums import PaymentStatus, InvoiceStatus, UnitStatus, MaintenanceStatus

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
    total_paid = Decimal("0")
    overdue_amount = Decimal("0")

    hour = datetime.now(ZoneInfo("Africa/Nairobi")).hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    first_name = (user.name or "").split(" ")[0] if user.name else ""

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
            total_paid += p.amount
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
            "total_paid": total_paid, "overdue_amount": overdue_amount,
            "greeting": greeting, "first_name": first_name,
        },
    )


@router.get("/admin/dashboard")
def admin_dashboard(request: Request, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    today = date.today()

    total_units = db.query(Unit).count()
    occupied_units = db.query(Unit).filter(Unit.status == UnitStatus.OCCUPIED).count()
    vacant_units = db.query(Unit).filter(Unit.status == UnitStatus.AVAILABLE).count()
    reserved_units = db.query(Unit).filter(Unit.status == UnitStatus.RESERVED).count()
    total_properties = db.query(Property).count()

    collected_this_month = Decimal("0")
    for p in db.query(Payment).filter(Payment.status == PaymentStatus.SUCCESSFUL):
        if p.payment_date.year == today.year and p.payment_date.month == today.month:
            collected_this_month += p.amount

    outstanding_invoices = db.query(Invoice).filter(
        Invoice.status.in_([InvoiceStatus.GENERATED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE])
    ).all()
    total_outstanding = sum((inv.balance for inv in outstanding_invoices), Decimal("0"))
    overdue_count = db.query(Invoice).filter(Invoice.status == InvoiceStatus.OVERDUE).count()

    open_maintenance = db.query(MaintenanceRequest).filter(
        MaintenanceRequest.status.in_([
            MaintenanceStatus.SUBMITTED, MaintenanceStatus.APPROVED,
            MaintenanceStatus.ASSIGNED, MaintenanceStatus.IN_PROGRESS,
        ])
    ).count()

    recent_payments = (
        db.query(Payment)
        .filter(Payment.status == PaymentStatus.SUCCESSFUL)
        .order_by(Payment.payment_date.desc())
        .limit(5)
        .all()
    )

    hour = datetime.now(ZoneInfo("Africa/Nairobi")).hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    first_name = (user.name or "").split(" ")[0] if user.name else ""

    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request, "user": user, "greeting": greeting, "first_name": first_name,
            "total_units": total_units, "occupied_units": occupied_units,
            "vacant_units": vacant_units, "reserved_units": reserved_units,
            "total_properties": total_properties,
            "collected_this_month": collected_this_month,
            "total_outstanding": total_outstanding, "overdue_count": overdue_count,
            "open_maintenance": open_maintenance, "recent_payments": recent_payments,
        },
    )


@router.get("/admin/more")
def admin_more(request: Request, user: User = Depends(require_staff)):
    return templates.TemplateResponse("admin/more.html", {"request": request, "user": user})
