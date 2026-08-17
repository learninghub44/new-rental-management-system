import json
import uuid

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_tenant
from app.core.templating import templates
from app.core.security import verify_password, hash_password
from app.models.user import User
from app.models.tenant import Tenant, Lease
from app.models.property import Property, Unit
from app.models.billing import Invoice
from app.models.payment import Payment, Receipt
from app.models.enums import InvoiceStatus, MaintenancePriority, ActivityAction, LeaseStatus
from app.schemas.payment import STKPushRequest
from app.schemas.maintenance import MaintenanceCreate
from app.services.billing_service import list_invoices
from app.services.payment_service import list_payments
from app.services.payhero_service import initiate_stk_push
from app.services.maintenance_service import create_request, list_requests, MaintenanceServiceError
from app.services.ledger_service import get_tenant_balance
from app.services.activity_log import log_activity

router = APIRouter(prefix="/tenant", tags=["tenant"])


def _current_tenant(db: Session, user: User) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.user_id == user.id).first()
    if not tenant:
        raise ValueError("No tenant profile linked to this account")
    return tenant


def _active_lease(db: Session, tenant: Tenant) -> Lease | None:
    lease = (
        db.query(Lease)
        .filter(Lease.tenant_id == tenant.id, Lease.status == LeaseStatus.ACTIVE)
        .order_by(Lease.start_date.desc())
        .first()
    )
    if not lease:
        # Fall back to the most recent lease of any status so tenants between
        # leases still see something rather than an empty section.
        lease = db.query(Lease).filter(Lease.tenant_id == tenant.id).order_by(Lease.start_date.desc()).first()
    return lease


@router.get("/rent")
def tenant_rent(request: Request, db: Session = Depends(get_db), user: User = Depends(require_tenant)):
    tenant = _current_tenant(db, user)
    balance = get_tenant_balance(db, tenant.id)
    invoices, _ = list_invoices(db, tenant_id=tenant.id, page=1, page_size=50)

    lease = _active_lease(db, tenant)
    unit = db.get(Unit, tenant.unit_id) if tenant.unit_id else (db.get(Unit, lease.unit_id) if lease else None)
    property_ = db.get(Property, tenant.property_id) if tenant.property_id else (db.get(Property, unit.property_id) if unit else None)
    manager = db.get(User, property_.manager_id) if property_ and property_.manager_id else None

    next_invoice = (
        db.query(Invoice)
        .filter(
            Invoice.tenant_id == tenant.id,
            Invoice.status.in_([InvoiceStatus.GENERATED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]),
        )
        .order_by(Invoice.due_date.asc())
        .first()
    )

    return templates.TemplateResponse(
        "tenant/rent.html",
        {
            "request": request, "user": user, "tenant": tenant, "balance": balance, "invoices": invoices,
            "lease": lease, "unit": unit, "property": property_, "manager": manager, "next_invoice": next_invoice,
        },
    )


@router.get("/payments")
def tenant_payments(request: Request, db: Session = Depends(get_db), user: User = Depends(require_tenant)):
    tenant = _current_tenant(db, user)
    payments, _ = list_payments(db, tenant_id=tenant.id, page=1, page_size=50)
    balance = get_tenant_balance(db, tenant.id)
    outstanding_invoices = (
        db.query(Invoice)
        .filter(Invoice.tenant_id == tenant.id, Invoice.status.in_([InvoiceStatus.GENERATED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]))
        .order_by(Invoice.due_date)
        .all()
    )
    unit = db.get(Unit, tenant.unit_id) if tenant.unit_id else None
    property_ = db.get(Property, tenant.property_id) if tenant.property_id else (db.get(Property, unit.property_id) if unit else None)

    receipts_by_payment = {}
    if payments:
        receipts = db.query(Receipt).filter(Receipt.payment_id.in_([p.id for p in payments])).all()
        receipts_by_payment = {r.payment_id: r for r in receipts}

    return templates.TemplateResponse(
        "tenant/payments.html",
        {
            "request": request, "user": user, "tenant": tenant, "payments": payments, "balance": balance,
            "outstanding_invoices": outstanding_invoices, "unit": unit, "property": property_,
            "receipts_by_payment": receipts_by_payment,
        },
    )


@router.post("/payments/pay")
def tenant_pay_submit(
    request: Request, invoice_id: str = Form(""), amount: str = Form(...), phone_number: str = Form(...),
    db: Session = Depends(get_db), user: User = Depends(require_tenant),
):
    tenant = _current_tenant(db, user)
    try:
        data = STKPushRequest(invoice_id=invoice_id or None, amount=amount, phone_number=phone_number)
        txn = initiate_stk_push(db, tenant, data)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    db.commit()

    if txn.checkout_request_id:
        return JSONResponse(
            {
                "status": "pending",
                "message": "Check your phone to complete the M-Pesa payment.",
                "payment_id": str(txn.payment_id),
            },
            headers={"HX-Trigger": json.dumps({"toast": {"type": "info", "message": "STK push sent — check your phone"}})},
        )
    return JSONResponse(
        {"status": "failed", "message": txn.error_reason or "Could not start the payment", "payment_id": str(txn.payment_id)},
        status_code=502,
        headers={"HX-Trigger": json.dumps({"toast": {"type": "error", "message": "Payment could not be started"}})},
    )


@router.get("/payments/status/{payment_id}")
def tenant_pay_status(
    request: Request, payment_id: str, db: Session = Depends(get_db), user: User = Depends(require_tenant),
):
    """Polled by the payment-processing screen so the tenant is never left wondering."""
    tenant = _current_tenant(db, user)
    try:
        pid = uuid.UUID(payment_id)
    except ValueError:
        return JSONResponse({"error": "Invalid payment id"}, status_code=400)

    payment = db.query(Payment).filter(Payment.id == pid, Payment.tenant_id == tenant.id).first()
    if not payment:
        return JSONResponse({"error": "Payment not found"}, status_code=404)

    receipt = db.query(Receipt).filter(Receipt.payment_id == payment.id).first()
    return JSONResponse({
        "status": payment.status.value,
        "amount": float(payment.amount),
        "payment_date": payment.payment_date.isoformat(),
        "method": payment.method.value,
        "reference": payment.transaction_id or payment.reference,
        "has_receipt": bool(receipt and receipt.pdf_url),
    })


@router.get("/payments/{payment_id}/receipt")
def tenant_payment_receipt(
    request: Request, payment_id: str, db: Session = Depends(get_db), user: User = Depends(require_tenant),
):
    tenant = _current_tenant(db, user)
    try:
        pid = uuid.UUID(payment_id)
    except ValueError:
        return templates.TemplateResponse("shared/error.html", {"request": request, "status_code": 404, "detail": "Receipt not found"}, status_code=404)

    payment = db.query(Payment).filter(Payment.id == pid, Payment.tenant_id == tenant.id).first()
    receipt = db.query(Receipt).filter(Receipt.payment_id == pid).first() if payment else None
    if not payment or not receipt or not receipt.pdf_url:
        return templates.TemplateResponse("shared/error.html", {"request": request, "status_code": 404, "detail": "Receipt not available"}, status_code=404)

    if receipt.pdf_url.startswith("/static"):
        file_path = "app/static" + receipt.pdf_url.split("/static", 1)[1]
        return FileResponse(file_path, media_type="application/pdf", filename=f"{receipt.receipt_number}.pdf")
    return RedirectResponse(url=receipt.pdf_url)


@router.get("/maintenance")
def tenant_maintenance_list(request: Request, db: Session = Depends(get_db), user: User = Depends(require_tenant)):
    tenant = _current_tenant(db, user)
    requests, _ = list_requests(db, tenant_id=tenant.id, page=1, page_size=50)
    return templates.TemplateResponse("tenant/maintenance.html", {"request": request, "user": user, "requests": requests})


@router.get("/maintenance/new")
def tenant_maintenance_new_form(request: Request, user: User = Depends(require_tenant)):
    return templates.TemplateResponse(
        "tenant/maintenance_form.html", {"request": request, "user": user, "priorities": list(MaintenancePriority)},
    )


@router.post("/maintenance/new")
def tenant_maintenance_create_submit(
    request: Request, title: str = Form(...), description: str = Form(...), priority: str = Form("medium"),
    db: Session = Depends(get_db), user: User = Depends(require_tenant),
):
    tenant = _current_tenant(db, user)
    try:
        data = MaintenanceCreate(title=title, description=description, priority=priority)
        item = create_request(db, tenant, data)
    except (MaintenanceServiceError, ValueError) as e:
        return templates.TemplateResponse(
            "tenant/maintenance_form.html",
            {"request": request, "user": user, "priorities": list(MaintenancePriority), "error": str(e)},
            status_code=400,
        )

    log_activity(db, ActivityAction.CREATE, user_id=user.id, entity_type="maintenance_request", entity_id=str(item.id),
                 description=f"Submitted maintenance request: {item.title}")
    db.commit()
    return RedirectResponse(url="/tenant/maintenance", status_code=303)


@router.get("/profile")
def tenant_profile(request: Request, db: Session = Depends(get_db), user: User = Depends(require_tenant)):
    tenant = _current_tenant(db, user)
    return templates.TemplateResponse("tenant/profile.html", {"request": request, "user": user, "tenant": tenant})


@router.post("/profile/change-password")
def tenant_change_password(
    request: Request, current_password: str = Form(...), new_password: str = Form(...),
    db: Session = Depends(get_db), user: User = Depends(require_tenant),
):
    tenant = _current_tenant(db, user)
    if not verify_password(current_password, user.password_hash):
        return templates.TemplateResponse(
            "tenant/profile.html", {"request": request, "user": user, "tenant": tenant, "error": "Current password is incorrect"}, status_code=400,
        )
    if len(new_password) < 8:
        return templates.TemplateResponse(
            "tenant/profile.html", {"request": request, "user": user, "tenant": tenant, "error": "New password must be at least 8 characters"}, status_code=400,
        )

    user.password_hash = hash_password(new_password)
    db.add(user)
    log_activity(db, ActivityAction.UPDATE, user_id=user.id, entity_type="user", entity_id=str(user.id), description="Tenant changed their password")
    db.commit()
    return templates.TemplateResponse("tenant/profile.html", {"request": request, "user": user, "tenant": tenant, "success": "Password updated"})
