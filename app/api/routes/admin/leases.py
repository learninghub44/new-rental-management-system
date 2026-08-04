import uuid

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.models.enums import ActivityAction
from app.schemas.lease import LeaseCreate, LeaseRenew
from app.services.lease_service import create_lease, renew_lease, terminate_lease, LeaseServiceError
from app.services.activity_log import log_activity
from app.core.templating import templates

router = APIRouter(prefix="/admin/tenants/{tenant_id}/leases", tags=["admin-leases"])


@router.post("")
def lease_create_submit(
    request: Request, tenant_id: uuid.UUID,
    unit_id: str = Form(...), start_date: str = Form(...), end_date: str = Form(""),
    rent_amount: str = Form(...), deposit: str = Form("0"),
    db: Session = Depends(get_db), user: User = Depends(require_admin),
):
    try:
        data = LeaseCreate(
            tenant_id=tenant_id, unit_id=uuid.UUID(unit_id), start_date=start_date,
            end_date=end_date or None, rent_amount=rent_amount, deposit=deposit or 0,
        )
        lease = create_lease(db, data)
    except (LeaseServiceError, ValueError) as e:
        from app.models.tenant import Tenant, Lease
        from app.models.property import Unit, Property
        from app.models.enums import LeaseStatus, UnitStatus
        tenant = db.get(Tenant, tenant_id)
        leases = db.query(Lease).filter(Lease.tenant_id == tenant_id).order_by(Lease.start_date.desc()).all()
        available_units = db.query(Unit).join(Property).filter(Unit.status == UnitStatus.AVAILABLE).order_by(Property.name, Unit.unit_number).all()
        return templates.TemplateResponse(
            "admin/tenants/detail.html",
            {"request": request, "user": user, "tenant": tenant, "leases": leases,
             "active_lease": next((l for l in leases if l.status == LeaseStatus.ACTIVE), None),
             "available_units": available_units, "error": str(e)},
            status_code=400,
        )

    log_activity(db, ActivityAction.CREATE, user_id=user.id, entity_type="lease", entity_id=str(lease.id),
                 description=f"Created lease for tenant {tenant_id}")
    db.commit()
    return RedirectResponse(url=f"/admin/tenants/{tenant_id}", status_code=303)


@router.post("/{lease_id}/renew")
def lease_renew_submit(
    request: Request, tenant_id: uuid.UUID, lease_id: uuid.UUID,
    new_end_date: str = Form(...), new_rent_amount: str = Form(""),
    db: Session = Depends(get_db), user: User = Depends(require_admin),
):
    try:
        data = LeaseRenew(new_end_date=new_end_date, new_rent_amount=new_rent_amount or None)
        renew_lease(db, lease_id, data)
    except (LeaseServiceError, ValueError):
        pass  # fall through to redirect; detail page shows current state either way
    else:
        log_activity(db, ActivityAction.UPDATE, user_id=user.id, entity_type="lease", entity_id=str(lease_id),
                     description="Renewed lease")
        db.commit()
    return RedirectResponse(url=f"/admin/tenants/{tenant_id}", status_code=303)


@router.post("/{lease_id}/terminate")
def lease_terminate_submit(request: Request, tenant_id: uuid.UUID, lease_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    try:
        terminate_lease(db, lease_id)
    except LeaseServiceError:
        pass
    else:
        log_activity(db, ActivityAction.UPDATE, user_id=user.id, entity_type="lease", entity_id=str(lease_id),
                     description="Terminated lease")
        db.commit()
    return RedirectResponse(url=f"/admin/tenants/{tenant_id}", status_code=303)
