import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.models.tenant import Tenant, Lease
from app.models.property import Unit
from app.models.enums import LeaseStatus, UnitStatus, TenantStatus
from app.schemas.lease import LeaseCreate, LeaseRenew


class LeaseServiceError(Exception):
    pass


def create_lease(db: Session, data: LeaseCreate) -> Lease:
    tenant = db.get(Tenant, data.tenant_id)
    if not tenant:
        raise LeaseServiceError("Tenant not found")

    unit = db.get(Unit, data.unit_id)
    if not unit:
        raise LeaseServiceError("Unit not found")
    if unit.status == UnitStatus.OCCUPIED:
        raise LeaseServiceError("This unit is already occupied")

    existing_active = (
        db.query(Lease)
        .filter(Lease.tenant_id == data.tenant_id, Lease.status == LeaseStatus.ACTIVE)
        .first()
    )
    if existing_active:
        raise LeaseServiceError("This tenant already has an active lease")

    lease = Lease(
        tenant_id=data.tenant_id,
        unit_id=data.unit_id,
        start_date=data.start_date,
        end_date=data.end_date,
        rent_amount=data.rent_amount,
        deposit=data.deposit,
        status=LeaseStatus.ACTIVE,
    )
    db.add(lease)

    # Sync tenant's current assignment + unit status.
    tenant.property_id = unit.property_id
    tenant.unit_id = unit.id
    tenant.monthly_rent = data.rent_amount
    tenant.deposit = data.deposit
    tenant.move_in_date = data.start_date
    tenant.status = TenantStatus.ACTIVE
    unit.status = UnitStatus.OCCUPIED

    db.add_all([tenant, unit])
    db.flush()
    return lease


def renew_lease(db: Session, lease_id: uuid.UUID, data: LeaseRenew) -> Lease:
    lease = db.get(Lease, lease_id)
    if not lease:
        raise LeaseServiceError("Lease not found")
    if lease.status != LeaseStatus.ACTIVE:
        raise LeaseServiceError("Only an active lease can be renewed")

    lease.end_date = data.new_end_date
    if data.new_rent_amount:
        lease.rent_amount = data.new_rent_amount
        tenant = db.get(Tenant, lease.tenant_id)
        if tenant:
            tenant.monthly_rent = data.new_rent_amount
            db.add(tenant)
    lease.status = LeaseStatus.RENEWED

    db.add(lease)
    db.flush()
    return lease


def terminate_lease(db: Session, lease_id: uuid.UUID) -> Lease:
    lease = db.get(Lease, lease_id)
    if not lease:
        raise LeaseServiceError("Lease not found")

    lease.status = LeaseStatus.TERMINATED
    lease.end_date = lease.end_date or date.today()

    unit = db.get(Unit, lease.unit_id)
    if unit:
        unit.status = UnitStatus.AVAILABLE
        db.add(unit)

    tenant = db.get(Tenant, lease.tenant_id)
    if tenant:
        tenant.unit_id = None
        tenant.property_id = None
        db.add(tenant)

    db.add(lease)
    db.flush()
    return lease


def list_expiring_leases(db: Session, within_days: int = 30) -> list[Lease]:
    from datetime import timedelta
    cutoff = date.today() + timedelta(days=within_days)
    return (
        db.query(Lease)
        .filter(Lease.status == LeaseStatus.ACTIVE, Lease.end_date.isnot(None), Lease.end_date <= cutoff)
        .order_by(Lease.end_date)
        .all()
    )
