import uuid

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse, FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin_or_accountant, require_staff
from app.core.templating import templates
from app.models.user import User
from app.models.tenant import Tenant
from app.models.payment import Payment, Receipt
from app.models.billing import Invoice
from app.models.enums import InvoiceStatus, ActivityAction
from app.schemas.payment import ManualPaymentCreate
from app.services.payment_service import record_manual_payment, list_payments, PaymentServiceError
from app.services.activity_log import log_activity
from app.services.email_service import send_payment_receipt_email

router = APIRouter(prefix="/admin/payments", tags=["admin-payments"])


@router.get("")
def payments_list(request: Request, page: int = 1, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    payments, total = list_payments(db, page=page)
    tenants_by_id = {t.id: t for t in db.query(Tenant).filter(Tenant.id.in_([p.tenant_id for p in payments])).all()} if payments else {}
    return templates.TemplateResponse(
        "admin/payments/list.html",
        {"request": request, "user": user, "payments": payments, "total": total, "page": page, "tenants_by_id": tenants_by_id},
    )


@router.get("/record")
def payment_record_form(request: Request, tenant_id: str = "", db: Session = Depends(get_db), user: User = Depends(require_admin_or_accountant)):
    tenants = db.query(Tenant).order_by(Tenant.full_name).all()
    outstanding_invoices = []
    if tenant_id:
        outstanding_invoices = (
            db.query(Invoice)
            .filter(Invoice.tenant_id == uuid.UUID(tenant_id), Invoice.status.in_([InvoiceStatus.GENERATED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]))
            .order_by(Invoice.due_date)
            .all()
        )
    return templates.TemplateResponse(
        "admin/payments/record_form.html",
        {"request": request, "user": user, "tenants": tenants, "selected_tenant_id": tenant_id, "outstanding_invoices": outstanding_invoices},
    )


@router.post("/record")
def payment_record_submit(
    request: Request,
    tenant_id: str = Form(...), invoice_id: str = Form(""), amount: str = Form(...),
    method: str = Form(...), reference: str = Form(""), payment_date: str = Form(...),
    db: Session = Depends(get_db), user: User = Depends(require_admin_or_accountant),
):
    try:
        data = ManualPaymentCreate(
            tenant_id=tenant_id, invoice_id=invoice_id or None, amount=amount,
            method=method, reference=reference or None, payment_date=payment_date,
        )
        payment = record_manual_payment(db, data, recorded_by_user_id=user.id)
    except (PaymentServiceError, ValueError) as e:
        tenants = db.query(Tenant).order_by(Tenant.full_name).all()
        return templates.TemplateResponse(
            "admin/payments/record_form.html",
            {"request": request, "user": user, "tenants": tenants, "selected_tenant_id": tenant_id,
             "outstanding_invoices": [], "error": str(e)},
            status_code=400,
        )

    tenant = db.get(Tenant, payment.tenant_id)
    if tenant and tenant.email:
        receipt = db.query(Receipt).filter(Receipt.payment_id == payment.id).first()
        send_payment_receipt_email(db, tenant.email, tenant.full_name, f"{payment.amount:,.2f}", receipt.receipt_number if receipt else "-")

    log_activity(db, ActivityAction.PAYMENT, user_id=user.id, entity_type="payment", entity_id=str(payment.id),
                 description=f"Recorded {payment.method.value} payment of {payment.amount} for tenant {tenant_id}")
    db.commit()
    return RedirectResponse(url=f"/admin/payments/{payment.id}", status_code=303)


@router.get("/{payment_id}")
def payment_detail(request: Request, payment_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    payment = db.get(Payment, payment_id)
    if not payment:
        return templates.TemplateResponse("shared/error.html", {"request": request, "status_code": 404, "detail": "Payment not found"}, status_code=404)
    tenant = db.get(Tenant, payment.tenant_id)
    receipt = db.query(Receipt).filter(Receipt.payment_id == payment.id).first()
    return templates.TemplateResponse(
        "admin/payments/detail.html", {"request": request, "user": user, "payment": payment, "tenant": tenant, "receipt": receipt},
    )


@router.get("/{payment_id}/receipt")
def payment_receipt_download(request: Request, payment_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    receipt = db.query(Receipt).filter(Receipt.payment_id == payment_id).first()
    if not receipt or not receipt.pdf_url:
        return templates.TemplateResponse("shared/error.html", {"request": request, "status_code": 404, "detail": "Receipt not available"}, status_code=404)
    file_path = "app/static" + receipt.pdf_url.split("/static", 1)[1]
    return FileResponse(file_path, media_type="application/pdf", filename=f"{receipt.receipt_number}.pdf")
