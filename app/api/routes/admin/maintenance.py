import uuid

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_staff
from app.core.templating import templates
from app.models.user import User
from app.models.tenant import Tenant
from app.models.maintenance import MaintenanceRequest
from app.models.enums import MaintenanceStatus, MaintenancePriority, ActivityAction, UserRole, UserStatus
from app.schemas.maintenance import MaintenanceUpdate
from app.services.maintenance_service import update_request, list_requests, MaintenanceServiceError
from app.services.activity_log import log_activity
from app.services.email_service import send_maintenance_update_email

router = APIRouter(prefix="/admin/maintenance", tags=["admin-maintenance"])


@router.get("")
def maintenance_list(
    request: Request, status_filter: str = "", page: int = 1,
    db: Session = Depends(get_db), user: User = Depends(require_staff),
):
    status_enum = MaintenanceStatus(status_filter) if status_filter else None
    requests, total = list_requests(db, status_filter=status_enum, page=page)
    tenants_by_id = {t.id: t for t in db.query(Tenant).filter(Tenant.id.in_([r.tenant_id for r in requests])).all()} if requests else {}
    return templates.TemplateResponse(
        "admin/maintenance/list.html",
        {"request": request, "user": user, "requests": requests, "total": total,
         "status_filter": status_filter, "statuses": list(MaintenanceStatus), "tenants_by_id": tenants_by_id},
    )


@router.get("/{request_id}")
def maintenance_detail(request: Request, request_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    maintenance_request = db.get(MaintenanceRequest, request_id)
    if not maintenance_request:
        return templates.TemplateResponse("shared/error.html", {"request": request, "status_code": 404, "detail": "Request not found"}, status_code=404)
    tenant = db.get(Tenant, maintenance_request.tenant_id)
    staff = db.query(User).filter(User.role.in_([UserRole.ADMIN, UserRole.CARETAKER]), User.status == UserStatus.ACTIVE).order_by(User.name).all()
    return templates.TemplateResponse(
        "admin/maintenance/detail.html",
        {"request": request, "user": user, "item": maintenance_request, "tenant": tenant, "staff": staff,
         "statuses": list(MaintenanceStatus), "priorities": list(MaintenancePriority)},
    )


@router.post("/{request_id}/update")
def maintenance_update_submit(
    request: Request, request_id: uuid.UUID,
    status_value: str = Form(..., alias="status"), priority: str = Form(""),
    assigned_to_user_id: str = Form(""), resolution_notes: str = Form(""),
    db: Session = Depends(get_db), user: User = Depends(require_staff),
):
    try:
        data = MaintenanceUpdate(
            status=status_value or None, priority=priority or None,
            assigned_to_user_id=assigned_to_user_id or None, resolution_notes=resolution_notes or None,
        )
        item = update_request(db, request_id, data)
    except (MaintenanceServiceError, ValueError):
        return RedirectResponse(url=f"/admin/maintenance/{request_id}", status_code=303)

    tenant = db.get(Tenant, item.tenant_id)
    if tenant and tenant.email:
        send_maintenance_update_email(db, tenant.email, tenant.full_name, item.title, item.status.value.replace("_", " ").title())

    log_activity(db, ActivityAction.UPDATE, user_id=user.id, entity_type="maintenance_request", entity_id=str(item.id),
                 description=f"Updated maintenance request to {item.status.value}")
    db.commit()
    return RedirectResponse(url=f"/admin/maintenance/{request_id}", status_code=303)
