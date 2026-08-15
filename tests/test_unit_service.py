import pytest
from datetime import date

from app.models.property import Property, Unit
from app.models.enums import PropertyStatus, UnitStatus, UnitType, LeaseStatus
from app.models.tenant import Lease
from app.schemas.unit import UnitUpdate
from app.services.unit_service import update_unit, UnitServiceError


def _make_occupied_unit_with_active_lease(db_session, make_tenant):
    prop = Property(name="P", location="loc", status=PropertyStatus.ACTIVE)
    db_session.add(prop)
    db_session.flush()
    unit = Unit(
        property_id=prop.id, unit_number="B1", unit_type=UnitType.STUDIO,
        status=UnitStatus.OCCUPIED, monthly_rent=1000,
    )
    db_session.add(unit)
    db_session.flush()

    tenant = make_tenant()
    lease = Lease(
        tenant_id=tenant.id, unit_id=unit.id, start_date=date(2026, 1, 1),
        rent_amount=1000, status=LeaseStatus.ACTIVE,
    )
    db_session.add(lease)
    db_session.flush()
    return unit, lease


def test_cannot_mark_occupied_unit_available_while_lease_active(db_session, make_tenant):
    unit, lease = _make_occupied_unit_with_active_lease(db_session, make_tenant)

    with pytest.raises(UnitServiceError):
        update_unit(db_session, unit.id, UnitUpdate(status=UnitStatus.AVAILABLE))

    assert unit.status == UnitStatus.OCCUPIED


def test_can_change_status_once_lease_is_no_longer_active(db_session, make_tenant):
    unit, lease = _make_occupied_unit_with_active_lease(db_session, make_tenant)
    lease.status = LeaseStatus.TERMINATED
    db_session.flush()

    updated = update_unit(db_session, unit.id, UnitUpdate(status=UnitStatus.AVAILABLE))
    assert updated.status == UnitStatus.AVAILABLE


def test_non_status_updates_still_work_on_occupied_unit(db_session, make_tenant):
    unit, lease = _make_occupied_unit_with_active_lease(db_session, make_tenant)
    updated = update_unit(db_session, unit.id, UnitUpdate(monthly_rent=1500))
    assert updated.monthly_rent == 1500
    assert updated.status == UnitStatus.OCCUPIED
