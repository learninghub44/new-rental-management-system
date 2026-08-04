import uuid

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin, require_admin_or_accountant, require_staff
from app.core.templating import templates
from app.models.user import User
from app.models.tenant import Tenant, Lease
from app.models.billing import Invoice, LedgerEntry
from app.models.payment import Payment
from app.models.enums import InvoiceStatus, LeaseStatus, ActivityAction
from app.schemas.billing import InvoiceCreate, InvoiceAdjust, MonthlyGenerateRequest
from app.services.billing_service import (
    create_invoice, generate_monthly_invoices, adjust_invoice, cancel_invoice,
    list_invoices, BillingServiceError,
)
from app.services.activity_log import log_activity
from app.services.email_service import send_invoice_notification_email

router = APIRouter(prefix="/admin/invoices", tags=["admin-billing"])


@router.get("")
def invoices_list(
    request: Request, status_filter: str = "", page: int = 1,
    db: Session = Depends(get_db), user: User = Depends(require_staff),
):
    status_enum = InvoiceStatus(status_filter) if status_filter else None
    invoices, total = list_invoices(db, status_filter=status_enum, page=page)
    return templates.TemplateResponse(
        "admin/invoices/list.html",
        {"request": request, "user": user, "invoices": invoices, "total": total,
         "status_filter": status_filter, "statuses": list(InvoiceStatus), "page": page},
    )


@router.get("/generate")
def invoices_generate_form(request: Request, user: User = Depends(require_admin_or_accountant)):
    return templates.TemplateResponse("admin/invoices/generate_form.html", {"request": request, "user": user})


@router.post("/generate")
def invoices_generate_submit(
    request: Request,
    billing_period_start: str = Form(...), billing_period_end: str = Form(...), due_date: str = Form(...),
    water: str = Form("0"), electricity: str = Form("0"), service_charges: str = Form("0"),
    db: Session = Depends(get_db), user: User = Depends(require_admin_or_accountant),
):
    try:
        data = MonthlyGenerateRequest(
            billing_period_start=billing_period_start, billing_period_end=billing_period_end, due_date=due_date,
            water=water or 0, electricity=electricity or 0, service_charges=service_charges or 0,
        )
        created = generate_monthly_invoices(db, data)
    except ValueError as e:
        return templates.TemplateResponse(
            "admin/invoices/generate_form.html", {"request": request, "user": user, "error": str(e)}, status_code=400,
        )

    for invoice in created:
        tenant = db.get(Tenant, invoice.tenant_id)
        if tenant and tenant.email:
            send_invoice_notification_email(
                db, tenant.email, tenant.full_name, invoice.invoice_number,
                f"{invoice.total_amount:,.2f}", invoice.due_date.strftime("%d %b %Y"),
            )

    log_activity(db, ActivityAction.CREATE, user_id=user.id, entity_type="invoice_batch",
                 description=f"Generated {len(created)} monthly invoices for {billing_period_start}")
    db.commit()
    return RedirectResponse(url="/admin/invoices", status_code=303)


@router.get("/{invoice_id}")
def invoice_detail(request: Request, invoice_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        return templates.TemplateResponse("shared/error.html", {"request": request, "status_code": 404, "detail": "Invoice not found"}, status_code=404)

    tenant = db.get(Tenant, invoice.tenant_id)
    payments = db.query(Payment).filter(Payment.invoice_id == invoice.id).order_by(Payment.payment_date.desc()).all()
    ledger_entries = db.query(LedgerEntry).filter(LedgerEntry.invoice_id == invoice.id).order_by(LedgerEntry.transaction_date).all()

    return templates.TemplateResponse(
        "admin/invoices/detail.html",
        {"request": request, "user": user, "invoice": invoice, "tenant": tenant,
         "payments": payments, "ledger_entries": ledger_entries},
    )


@router.post("/{invoice_id}/adjust")
def invoice_adjust_submit(
    request: Request, invoice_id: uuid.UUID,
    penalties: str = Form(""), discounts: str = Form(""), notes: str = Form(""),
    db: Session = Depends(get_db), user: User = Depends(require_admin_or_accountant),
):
    try:
        data = InvoiceAdjust(penalties=penalties or None, discounts=discounts or None, notes=notes or None)
        adjust_invoice(db, invoice_id, data)
    except (BillingServiceError, ValueError):
        pass
    else:
        log_activity(db, ActivityAction.UPDATE, user_id=user.id, entity_type="invoice", entity_id=str(invoice_id),
                     description="Adjusted invoice charges")
        db.commit()
    return RedirectResponse(url=f"/admin/invoices/{invoice_id}", status_code=303)


@router.post("/{invoice_id}/cancel")
def invoice_cancel_submit(request: Request, invoice_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    import json
    try:
        cancel_invoice(db, invoice_id)
    except BillingServiceError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    log_activity(db, ActivityAction.UPDATE, user_id=user.id, entity_type="invoice", entity_id=str(invoice_id),
                 description="Cancelled invoice")
    db.commit()
    return JSONResponse({"status": "cancelled"}, headers={"HX-Trigger": json.dumps({"toast": {"type": "success", "message": "Invoice cancelled"}})})


# --- Manual, per-tenant invoice creation lives under /admin/tenants/{id}/invoices ---
tenant_router = APIRouter(prefix="/admin/tenants/{tenant_id}/invoices", tags=["admin-billing"])


@tenant_router.get("/new")
def tenant_invoice_new_form(request: Request, tenant_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_admin_or_accountant)):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        return templates.TemplateResponse("shared/error.html", {"request": request, "status_code": 404, "detail": "Tenant not found"}, status_code=404)
    active_lease = db.query(Lease).filter(Lease.tenant_id == tenant_id, Lease.status == LeaseStatus.ACTIVE).first()
    return templates.TemplateResponse(
        "admin/invoices/form.html", {"request": request, "user": user, "tenant": tenant, "active_lease": active_lease},
    )


@tenant_router.post("/new")
def tenant_invoice_create_submit(
    request: Request, tenant_id: uuid.UUID,
    billing_period_start: str = Form(...), billing_period_end: str = Form(...), due_date: str = Form(...),
    rent: str = Form("0"), water: str = Form("0"), electricity: str = Form("0"),
    service_charges: str = Form("0"), penalties: str = Form("0"), discounts: str = Form("0"),
    notes: str = Form(""),
    db: Session = Depends(get_db), user: User = Depends(require_admin_or_accountant),
):
    active_lease = db.query(Lease).filter(Lease.tenant_id == tenant_id, Lease.status == LeaseStatus.ACTIVE).first()
    try:
        data = InvoiceCreate(
            tenant_id=str(tenant_id), lease_id=str(active_lease.id) if active_lease else None,
            billing_period_start=billing_period_start, billing_period_end=billing_period_end, due_date=due_date,
            rent=rent or 0, water=water or 0, electricity=electricity or 0,
            service_charges=service_charges or 0, penalties=penalties or 0, discounts=discounts or 0,
            notes=notes or None,
        )
        invoice = create_invoice(db, data)
    except (BillingServiceError, ValueError) as e:
        tenant = db.get(Tenant, tenant_id)
        return templates.TemplateResponse(
            "admin/invoices/form.html",
            {"request": request, "user": user, "tenant": tenant, "active_lease": active_lease, "error": str(e)},
            status_code=400,
        )

    tenant = db.get(Tenant, tenant_id)
    if tenant and tenant.email:
        send_invoice_notification_email(
            db, tenant.email, tenant.full_name, invoice.invoice_number,
            f"{invoice.total_amount:,.2f}", invoice.due_date.strftime("%d %b %Y"),
        )

    log_activity(db, ActivityAction.CREATE, user_id=user.id, entity_type="invoice", entity_id=str(invoice.id),
                 description=f"Created invoice {invoice.invoice_number}")
    db.commit()
    return RedirectResponse(url=f"/admin/invoices/{invoice.id}", status_code=303)
