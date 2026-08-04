import json

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_tenant
from app.core.templating import templates
from app.core.security import verify_password, hash_password
from app.models.user import User
from app.models.tenant import Tenant
from app.models.billing import Invoice, LedgerEntry
from app.models.payment import Payment
from app.models.enums import InvoiceStatus, MaintenancePriority, ActivityAction
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


@router.get("/rent")
def tenant_rent(request: Request, db: Session = Depends(get_db), user: User = Depends(require_tenant)):
    tenant = _current_tenant(db, user)
    balance = get_tenant_balance(db, tenant.id)
    invoices, _ = list_invoices(db, tenant_id=tenant.id, page=1, page_size=50)
    return templates.TemplateResponse(
        "tenant/rent.html", {"request": request, "user": user, "tenant": tenant, "balance": balance, "invoices": invoices},
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
    return templates.TemplateResponse(
        "tenant/payments.html",
        {"request": request, "user": user, "tenant": tenant, "payments": payments, "balance": balance, "outstanding_invoices": outstanding_invoices},
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
            {"status": "pending", "message": "Check your phone to complete the M-Pesa payment."},
            headers={"HX-Trigger": json.dumps({"toast": {"type": "info", "message": "STK push sent — check your phone"}})},
        )
    return JSONResponse(
        {"status": "failed", "message": txn.error_reason or "Could not start the payment"},
        status_code=502,
        headers={"HX-Trigger": json.dumps({"toast": {"type": "error", "message": "Payment could not be started"}})},
    )


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
