"""
Shared test fixtures. Uses an in-memory SQLite DB rather than Postgres —
the models use plain SQLAlchemy types (UUID/JSON/Enum) that SQLAlchemy
maps to SQLite equivalents, so this is safe for the service-layer logic
under test here. It is NOT a substitute for testing against real Postgres
before a release (see README's "Local development" for that).
"""
import os
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("SECRET_KEY", "test-secret-key")
# app.core.database creates its module-level engine eagerly with pool_size/
# max_overflow (QueuePool-only kwargs), so DATABASE_URL must resolve to a
# dialect that uses QueuePool — it's never actually connected to in tests,
# every test uses its own isolated in-memory SQLite engine instead (below).
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://test:test@localhost/test")

from app.core.database import Base  # noqa: E402
from app.models.tenant import Tenant, Lease  # noqa: E402
from app.models.property import Property, Unit  # noqa: E402
from app.models.enums import TenantStatus, LeaseStatus, PropertyStatus, UnitStatus, UnitType  # noqa: E402

# Import every model module so all tables register on Base.metadata before create_all.
from app.models import user, billing, payment, expense, maintenance, system  # noqa: E402,F401


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def make_tenant(db_session):
    def _make(**kwargs):
        defaults = dict(
            full_name="Test Tenant",
            phone=f"07{uuid.uuid4().int % 10**8:08d}",
            national_id=str(uuid.uuid4().int % 10**8),
            status=TenantStatus.ACTIVE,
        )
        defaults.update(kwargs)
        tenant = Tenant(**defaults)
        db_session.add(tenant)
        db_session.flush()
        return tenant
    return _make


@pytest.fixture()
def make_lease(db_session):
    def _make(tenant, rent_amount, **kwargs):
        prop = Property(name="Test Property", location="123 Test St", status=PropertyStatus.ACTIVE)
        db_session.add(prop)
        db_session.flush()
        unit = Unit(
            property_id=prop.id, unit_number="A1", unit_type=UnitType.ONE_BEDROOM,
            status=UnitStatus.OCCUPIED, monthly_rent=rent_amount,
        )
        db_session.add(unit)
        db_session.flush()

        defaults = dict(
            tenant_id=tenant.id, unit_id=unit.id, start_date=date(2026, 1, 1),
            rent_amount=rent_amount, status=LeaseStatus.ACTIVE,
        )
        defaults.update(kwargs)
        lease = Lease(**defaults)
        db_session.add(lease)
        db_session.flush()
        return lease
    return _make
