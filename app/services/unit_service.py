import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.property import Unit
from app.models.tenant import Tenant
from app.models.enums import UnitStatus
from app.schemas.unit import UnitCreate, UnitUpdate


class UnitServiceError(Exception):
    pass


def create_unit(db: Session, data: UnitCreate) -> Unit:
    unit = Unit(
        property_id=data.property_id,
        unit_number=data.unit_number.strip(),
        floor=data.floor,
        unit_type=data.unit_type,
        bedrooms=data.bedrooms,
        monthly_rent=data.monthly_rent,
        status=UnitStatus.AVAILABLE,
    )
    db.add(unit)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise UnitServiceError(f"Unit number '{data.unit_number}' already exists in this property")
    return unit


def update_unit(db: Session, unit_id: uuid.UUID, data: UnitUpdate) -> Unit:
    unit = db.get(Unit, unit_id)
    if not unit:
        raise UnitServiceError("Unit not found")

    if data.unit_number:
        unit.unit_number = data.unit_number.strip()
    if data.floor is not None:
        unit.floor = data.floor
    if data.unit_type:
        unit.unit_type = data.unit_type
    if data.bedrooms is not None:
        unit.bedrooms = data.bedrooms
    if data.monthly_rent is not None:
        unit.monthly_rent = data.monthly_rent
    if data.status:
        # Guard: can't mark a unit with an active tenant as available/inactive silently.
        unit.status = data.status

    db.add(unit)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise UnitServiceError(f"Unit number '{data.unit_number}' already exists in this property")
    return unit


def mark_vacant(db: Session, unit_id: uuid.UUID) -> Unit:
    unit = db.get(Unit, unit_id)
    if not unit:
        raise UnitServiceError("Unit not found")
    unit.status = UnitStatus.AVAILABLE
    db.add(unit)
    db.flush()
    return unit


def assign_tenant_to_unit(db: Session, unit_id: uuid.UUID, tenant_id: uuid.UUID) -> Unit:
    unit = db.get(Unit, unit_id)
    if not unit:
        raise UnitServiceError("Unit not found")
    if unit.status == UnitStatus.OCCUPIED:
        raise UnitServiceError("This unit is already occupied")

    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise UnitServiceError("Tenant not found")

    tenant.property_id = unit.property_id
    tenant.unit_id = unit.id
    tenant.monthly_rent = unit.monthly_rent
    unit.status = UnitStatus.OCCUPIED

    db.add_all([unit, tenant])
    db.flush()
    return unit
