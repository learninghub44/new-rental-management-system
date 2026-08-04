import uuid

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin, require_staff
from app.core.templating import templates
from app.models.user import User
from app.models.tenant import Tenant, Lease
from app.models.property import Property, Unit
from app.models.enums import TenantStatus, LeaseStatus, UnitStatus, ActivityAction
from app.schemas.tenant import TenantCreate, TenantUpdate
from app.services.tenant_service import list_tenants, create_tenant, update_tenant, move_tenant_out, TenantServiceError
from app.services.activity_log import log_activity
from app.services.email_service import send_welcome_email

router = APIRouter(prefix="/admin/tenants", tags=["admin-tenants"])


@router.get("")
def tenants_list(
    request: Request, search: str = "", status_filter: str = "", page: int = 1,
    db: Session = Depends(get_db), user: User = Depends(require_staff),
):
    status_enum = TenantStatus(status_filter) if status_filter else None
    tenants, total = list_tenants(db, search=search or None, status_filter=status_enum, page=page)
    return templates.TemplateResponse(
        "admin/tenants/list.html",
        {"request": request, "user": user, "tenants": tenants, "total": total,
         "search": search, "status_filter": status_filter, "statuses": list(TenantStatus)},
    )


@router.get("/new")
def tenant_new_form(request: Request, user: User = Depends(require_admin)):
    return templates.TemplateResponse("admin/tenants/form.html", {"request": request, "user": user, "mode": "create"})


@router.post("/new")
def tenant_create_submit(
    request: Request,
    full_name: str = Form(...), phone: str = Form(...), email: str = Form(""),
    national_id: str = Form(...), emergency_contact_name: str = Form(""),
    emergency_contact_phone: str = Form(""), create_login: bool = Form(True),
    db: Session = Depends(get_db), user: User = Depends(require_admin),
):
    try:
        data = TenantCreate(
            full_name=full_name, phone=phone, email=email or None, national_id=national_id,
            emergency_contact_name=emergency_contact_name or None,
            emergency_contact_phone=emergency_contact_phone or None, create_login=create_login,
        )
        tenant, default_password = create_tenant(db, data)
    except (TenantServiceError, ValueError) as e:
        return templates.TemplateResponse(
            "admin/tenants/form.html",
            {"request": request, "user": user, "mode": "create", "error": str(e)},
            status_code=400,
        )

    log_activity(db, ActivityAction.CREATE, user_id=user.id, entity_type="tenant", entity_id=str(tenant.id),
                 description=f"Created tenant {tenant.full_name}")
    if tenant.email and default_password:
        send_welcome_email(db, tenant.email, tenant.full_name)
    db.commit()

    if default_password:
        return templates.TemplateResponse(
            "admin/tenants/created.html",
            {"request": request, "user": user, "tenant": tenant, "default_password": default_password},
        )
    return RedirectResponse(url=f"/admin/tenants/{tenant.id}", status_code=303)


@router.get("/{tenant_id}")
def tenant_detail(request: Request, tenant_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        return templates.TemplateResponse("shared/error.html", {"request": request, "status_code": 404, "detail": "Tenant not found"}, status_code=404)

    leases = db.query(Lease).filter(Lease.tenant_id == tenant_id).order_by(Lease.start_date.desc()).all()
    active_lease = next((l for l in leases if l.status == LeaseStatus.ACTIVE), None)

    # Available units for the "start a lease" action, across all properties.
    available_units = (
        db.query(Unit).join(Property).filter(Unit.status == UnitStatus.AVAILABLE)
        .order_by(Property.name, Unit.unit_number).all()
    )

    return templates.TemplateResponse(
        "admin/tenants/detail.html",
        {"request": request, "user": user, "tenant": tenant, "leases": leases,
         "active_lease": active_lease, "available_units": available_units},
    )


@router.get("/{tenant_id}/edit")
def tenant_edit_form(request: Request, tenant_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        return templates.TemplateResponse("shared/error.html", {"request": request, "status_code": 404, "detail": "Tenant not found"}, status_code=404)
    return templates.TemplateResponse(
        "admin/tenants/form.html", {"request": request, "user": user, "mode": "edit", "target": tenant, "statuses": list(TenantStatus)}
    )


@router.post("/{tenant_id}/edit")
def tenant_edit_submit(
    request: Request, tenant_id: uuid.UUID,
    full_name: str = Form(...), phone: str = Form(...), email: str = Form(""),
    national_id: str = Form(...), emergency_contact_name: str = Form(""),
    emergency_contact_phone: str = Form(""), status_value: str = Form(..., alias="status"),
    db: Session = Depends(get_db), user: User = Depends(require_admin),
):
    try:
        data = TenantUpdate(
            full_name=full_name, phone=phone, email=email or None, national_id=national_id,
            emergency_contact_name=emergency_contact_name or None,
            emergency_contact_phone=emergency_contact_phone or None, status=TenantStatus(status_value),
        )
        tenant = update_tenant(db, tenant_id, data)
    except (TenantServiceError, ValueError) as e:
        target = db.get(Tenant, tenant_id)
        return templates.TemplateResponse(
            "admin/tenants/form.html",
            {"request": request, "user": user, "mode": "edit", "target": target, "statuses": list(TenantStatus), "error": str(e)},
            status_code=400,
        )

    log_activity(db, ActivityAction.UPDATE, user_id=user.id, entity_type="tenant", entity_id=str(tenant.id),
                 description=f"Updated tenant {tenant.full_name}")
    db.commit()
    return RedirectResponse(url=f"/admin/tenants/{tenant.id}", status_code=303)


@router.post("/{tenant_id}/move-out")
def tenant_move_out(request: Request, tenant_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    import json
    tenant = move_tenant_out(db, tenant_id)
    log_activity(db, ActivityAction.UPDATE, user_id=user.id, entity_type="tenant", entity_id=str(tenant_id),
                 description=f"Moved out tenant {tenant.full_name}")
    db.commit()
    return JSONResponse({"status": "moved_out"}, headers={"HX-Trigger": json.dumps({"toast": {"type": "success", "message": f"{tenant.full_name} marked moved out"}})})
